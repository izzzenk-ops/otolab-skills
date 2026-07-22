#!/usr/bin/env python3
"""文字起こしが「本物のナレーション」か「BGM/幻覚（＝テロップ主体アカウント）」かを判定する。

使い方:
  python3 detect_narration.py <reels_dir>

reels_dir/transcripts/*.txt を読み、各リールを narration / bgm に分類。
過半数が bgm なら「テロップ主体アカウント」と判定し、フレームからのテロップ読取を推奨する。
結果は stdout と reels_dir/transcripts/narration_verdict.json に出す。

なぜ必要か: ナレーションなし・BGM＋画面テロップで作るアカウントは、音声文字起こしが
「ご視聴ありがとうございました」等のBGM幻覚になり内容分析に使えない。その場合は
telop_frames.py で動画フレームを抜き、画面のテロップを実読する運用に切り替える。
"""
import json
import pathlib
import re
import sys
from collections import Counter

# Whisperが無音/BGMに対して吐きやすい幻覚・定型句
JUNK_MARKERS = [
    "ご視聴ありがとう", "ご清聴ありがとう", "おやすみなさい", "チャンネル登録",
    "thank you for watching", "thanks for watching", "please subscribe",
    "字幕", "transcribed by", "アンチャンネル",
]


def repetition_ratio(text):
    """最頻フレーズ（読点/改行区切り）が全体に占める割合。高いほど幻覚っぽい。"""
    parts = [p for p in re.split(r"[。\n、]", text) if len(p.strip()) >= 4]
    if not parts:
        return 1.0
    c = Counter(p.strip() for p in parts)
    return c.most_common(1)[0][1] / len(parts)


def classify(text):
    t = text.strip()
    low = t.lower()
    junk_hits = sum(1 for m in JUNK_MARKERS if m.lower() in low)
    # 幻覚の定型句を除いた「実質テキスト」
    stripped = t
    for m in JUNK_MARKERS:
        stripped = re.sub(re.escape(m), "", stripped, flags=re.I)
    stripped = re.sub(r"\s+", "", stripped)
    uniq_chars = len(set(stripped))
    rep = repetition_ratio(t)

    reasons = []
    score = 0  # 高いほど bgm/幻覚
    if junk_hits:
        score += 2 * junk_hits
        reasons.append(f"定型幻覚句x{junk_hits}")
    if len(stripped) < 25:
        score += 2
        reasons.append(f"実質{len(stripped)}文字と少")
    if uniq_chars < 20:
        score += 1
        reasons.append(f"語彙{uniq_chars}種と貧弱")
    if rep > 0.4:
        score += 2
        reasons.append(f"反復率{rep:.0%}")
    return ("bgm" if score >= 3 else "narration"), reasons


def main():
    reels_dir = pathlib.Path(sys.argv[1])
    tdir = reels_dir / "transcripts"
    files = sorted(tdir.glob("*.txt"))
    if not files:
        print("文字起こしが見つかりません:", tdir)
        sys.exit(1)

    results = {}
    bgm = 0
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        label, reasons = classify(text)
        results[f.stem] = {"label": label, "reasons": reasons,
                           "head": text.strip()[:40]}
        if label == "bgm":
            bgm += 1

    n = len(files)
    telop_driven = bgm >= n * 0.5
    verdict = {
        "total": n, "bgm": bgm, "narration": n - bgm,
        "telop_driven": telop_driven,
        "recommendation": (
            "テロップ主体アカウント。音声文字起こしは使わず、telop_frames.py で"
            "動画フレームを抜いて画面テロップを実読すること。"
            if telop_driven else
            "ナレーションあり。文字起こしをそのまま台本分析に使ってよい。"),
        "per_reel": results,
    }
    (tdir / "narration_verdict.json").write_text(
        json.dumps(verdict, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"判定: {bgm}/{n} 本がBGM/幻覚 → "
          f"{'★テロップ主体アカウント（フレーム読取へ）' if telop_driven else 'ナレーションあり（文字起こし使用）'}")
    for rid, r in results.items():
        mark = "BGM " if r["label"] == "bgm" else "ナレ"
        print(f"  [{mark}] {rid}: {r['head']}")
    print(f"-> {tdir / 'narration_verdict.json'}")


if __name__ == "__main__":
    main()
