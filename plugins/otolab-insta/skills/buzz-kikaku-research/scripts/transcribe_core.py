#!/usr/bin/env python3
"""文字起こしの共通エンジン（Mac / Windows 両対応）。

バックエンドをプラットフォームで自動切替する:
  - mlx_whisper が入っている（Apple Silicon Mac）→ mlx で重複ウィンドウ方式（高速・Metal）
  - 無ければ faster_whisper（Windows/Linux/Intel Mac）→ 内蔵VADで全区間を拾う

音声のデコードは imageio-ffmpeg 同梱のffmpegバイナリで行うので、
システムにffmpeg/Homebrewが無くても動く（完全クロスプラットフォーム）。

なぜ単発の whisper.transcribe(mp4) をやめたか:
  冒頭がBGMのみ・途中に無音があるリールで、中盤のナレーションを丸ごと欠落
  させる事故があった（mlxはシーク破綻、faster-whisperも素だと落ちる）。
  mlxは重複窓で、faster-whisperはVADで、それぞれ全区間を確実に舐める。

テスト用に環境変数 BUNSEKI_WHISPER_BACKEND=mlx|faster でバックエンドを強制できる。
"""
import difflib
import os
import subprocess

import numpy as np

# ---- バックエンド判定 -------------------------------------------------------
_FORCE = os.environ.get("BUNSEKI_WHISPER_BACKEND", "").strip().lower()
BACKEND = None
if _FORCE in ("mlx", "faster"):
    BACKEND = _FORCE
else:
    try:
        import mlx_whisper  # noqa: F401  (Apple Silicon)
        BACKEND = "mlx"
    except Exception:
        BACKEND = "faster"

MLX_MODEL = "mlx-community/whisper-large-v3-turbo"
FW_MODEL = os.environ.get("BUNSEKI_FW_MODEL", "large-v3")  # faster-whisper用
SR = 16000
WIN, HOP = 14.0, 10.0                       # mlx重複窓: 14秒・10秒ごと
TEMPS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]      # 温度フォールバック

_fw_model = None                            # faster-whisperモデルの遅延ロード


def _ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def decode_audio(path, sr=SR):
    """imageio-ffmpeg同梱ffmpegで16kHz mono float32 numpyにデコード（OS非依存）。"""
    ff = _ffmpeg_exe()
    out = subprocess.run(
        [ff, "-v", "error", "-i", str(path),
         "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
        capture_output=True).stdout
    return np.frombuffer(out, np.int16).astype(np.float32) / 32768.0


def _merge(raw):
    """重複ウィンドウで生じた重複・言い直しを畳む（mlx用）。"""
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
    return merged


def _transcribe_mlx(audio, language):
    import mlx_whisper
    dur = len(audio) / SR
    raw = []
    t = 0.0
    while t < dur:
        chunk = audio[int(t * SR):int((t + WIN) * SR)]
        r = mlx_whisper.transcribe(
            chunk, path_or_hf_repo=MLX_MODEL, language=language,
            condition_on_previous_text=False, temperature=TEMPS)
        for s in r.get("segments", []):
            tx = s["text"].strip()
            if tx:
                raw.append({"start": round(t + s["start"], 1),
                            "end": round(t + s["end"], 1), "text": tx})
        t += HOP
    merged = _merge(raw)
    return "".join(s["text"] for s in merged), merged, dur


def _load_fw():
    global _fw_model
    if _fw_model is not None:
        return _fw_model
    from faster_whisper import WhisperModel
    device, compute = "cpu", "int8"
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:      # GPU搭載Windows等
            device, compute = "cuda", "float16"
    except Exception:
        pass
    _fw_model = WhisperModel(FW_MODEL, device=device, compute_type=compute)
    return _fw_model


def _transcribe_faster(audio, language):
    model = _load_fw()
    dur = len(audio) / SR
    segments, _ = model.transcribe(
        audio, language=language, vad_filter=True,
        condition_on_previous_text=False, temperature=TEMPS)
    segs = []
    for s in segments:
        tx = s.text.strip()
        if tx:
            segs.append({"start": round(s.start, 1),
                         "end": round(s.end, 1), "text": tx})
    return "".join(s["text"] for s in segs), segs, dur


def transcribe_chunked(path, language="ja"):
    """パスから全文を文字起こしして返す。

    path は mp4 でも wav でもよい。
    returns (full_text, segments[{start,end,text}], duration_sec)
    """
    audio = decode_audio(path)
    if BACKEND == "mlx":
        return _transcribe_mlx(audio, language)
    return _transcribe_faster(audio, language)


def check_transcript(full, segs, dur):
    """文字起こしが壊れていないか自己診断し、警告文（or None）を返す。

    空・尺超過・幻覚ループを検知。引っかかったら「対象がそう」でなく
    「取得が壊れた」と疑い、映像（フレーム）で裏を取ること。
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
