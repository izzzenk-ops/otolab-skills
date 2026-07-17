#!/usr/bin/env python3
"""ダウンロード済みリール動画（mp4）をmlx_whisperで一括文字起こしする。

必ず ~/telop-tool/venv/bin/python3 で実行すること（mlx_whisperが入っている）:
  ~/telop-tool/venv/bin/python3 transcribe.py <video_dir> [--language ja]

出力（<video_dir>/transcripts/ に保存）:
  <リールID>.txt           — 全文
  <リールID>.segments.json — タイムスタンプ付きセグメント（冒頭フックの特定用）

すでに .txt が存在する動画はスキップする（再実行しても安全）。
"""
import json
import pathlib
import sys

from transcribe_core import MODEL, check_transcript, transcribe_chunked


def main():
    args = sys.argv[1:]
    language = "ja"
    if "--language" in args:
        language = args[args.index("--language") + 1]
    video_dir = pathlib.Path(args[0])
    out = video_dir / "transcripts"
    out.mkdir(exist_ok=True)

    videos = sorted(video_dir.glob("*.mp4"))
    print(f"{len(videos)} videos to transcribe (model: {MODEL})", flush=True)
    for i, v in enumerate(videos):
        txt_path = out / f"{v.stem}.txt"
        if txt_path.exists():
            print(f"[{i + 1}/{len(videos)}] SKIP (done) {v.name}", flush=True)
            continue
        try:
            full, segs, dur = transcribe_chunked(v, language)
            txt_path.write_text(full, encoding="utf-8")
            (out / f"{v.stem}.segments.json").write_text(
                json.dumps(segs, ensure_ascii=False, indent=1),
                encoding="utf-8")
            head = full[:40].replace("\n", " ")
            print(f"[{i + 1}/{len(videos)}] OK {v.name}: {head}...", flush=True)
            warn = check_transcript(full, segs, dur)
            if warn:
                print(f"    ⚠ 要確認 {v.name}: {warn}", flush=True)
        except Exception as e:
            print(f"[{i + 1}/{len(videos)}] FAILED {v.name}: {e}", flush=True)
    print(f"done -> {out}")


if __name__ == "__main__":
    main()
