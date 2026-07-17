#!/usr/bin/env python3
"""文字起こしの共通エンジン（重複ウィンドウ方式）。

transcribe.py / pipeline.py の両方がこれを使う。

なぜ単発の mlx_whisper.transcribe(mp4) をやめたか:
  冒頭がBGMのみ・途中に無音があるリールで、Whisperが無音判定でシークを飛ばし
  中盤のナレーションを丸ごと欠落させる事故があった（bunseki-reel開発時に発覚）。
  固定窓を重複させて全区間を強制的に舐めることで、この欠落を防ぐ。
"""
import difflib

import mlx_whisper
from mlx_whisper.audio import SAMPLE_RATE, load_audio

MODEL = "mlx-community/whisper-large-v3-turbo"
WIN, HOP = 14.0, 10.0                       # 窓14秒・10秒ごと（4秒重複）
TEMPS = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)      # 温度フォールバック


def transcribe_chunked(path, language="ja"):
    """重複ウィンドウで全体を文字起こしし、重複を畳んで返す。

    path は mp4 でも wav でもよい（load_audio がffmpegで16kHz monoに decode）。
    returns (full_text, segments[{start,end,text}], duration_sec)
    """
    audio = load_audio(str(path))
    dur = len(audio) / SAMPLE_RATE
    raw = []
    t = 0.0
    while t < dur:
        chunk = audio[int(t * SAMPLE_RATE):int((t + WIN) * SAMPLE_RATE)]
        r = mlx_whisper.transcribe(
            chunk, path_or_hf_repo=MODEL, language=language,
            condition_on_previous_text=False, temperature=TEMPS)
        for s in r.get("segments", []):
            tx = s["text"].strip()
            if tx:
                raw.append({"start": round(t + s["start"], 1),
                            "end": round(t + s["end"], 1), "text": tx})
        t += HOP
    raw.sort(key=lambda s: s["start"])

    merged = []
    for s in raw:
        if merged:
            prev = merged[-1]["text"]
            ratio = difflib.SequenceMatcher(None, prev, s["text"]).ratio()
            if s["text"] in prev or prev in s["text"] or ratio >= 0.5:
                if len(s["text"]) > len(prev):
                    merged[-1] = s
                continue
        merged.append(s)
    full = "".join(s["text"] for s in merged)
    return full, merged, dur


def check_transcript(full, segs, dur):
    """文字起こしが壊れていないか自己診断し、警告文（or None）を返す。

    空・尺超過・幻覚ループを検知。引っかかったら「対象がそう」でなく
    「取得が壊れた」と疑い、映像で裏を取ること。
    """
    text = (full or "").strip()
    if dur and dur >= 12 and len(text) < 8:
        return "文字起こしがほぼ空。ナレーション無しと即断せず映像で口の動きを確認"
    if dur and segs:
        max_end = max(s.get("end", 0) for s in segs)
        if max_end > dur + 5:
            return (f"セグメント終端{max_end:.0f}sが尺{dur:.0f}sを超過＝破綻の疑い。"
                    "結論に使う前に要確認")
    uniq = {s["text"] for s in segs if s.get("text")}
    if segs and len(segs) >= 3 and len(uniq) == 1:
        return "同一テキストの繰り返し（幻覚ループ）。文字起こしを信用しない"
    return None
