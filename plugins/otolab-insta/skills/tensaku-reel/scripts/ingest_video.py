#!/usr/bin/env python3
"""ローカル動画ファイルを添削用に取り込む（投稿前のリールを直接受け取る入口）。

setup.py が作った venv の python で実行すること:
  <venv>/bin/python ingest_video.py <video_path> <out_dir> [--language ja]

動作（fetch_reel.py のローカルファイル版。出力形式は揃えてある）:
  1. 動画を <out_dir>/ にコピー（ファイル名は元のまま。日本語名はASCII安全な名前に直す）
  2. カバー画像（0.1秒地点のフレーム）を <out_dir>/<stem>.jpg に抽出
  3. 尺を測って <out_dir>/data/meta.json に保存（source: "local_file"）
  4. 音声を文字起こし → data/transcript.txt / transcript.segments.json
     （バックエンドは transcribe_core が自動選択）

済みファイルはスキップ。OS非依存（ffmpegは imageio-ffmpeg 同梱バイナリ）。
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys

import imageio_ffmpeg

from transcribe_core import BACKEND, check_transcript, transcribe_chunked

FF = imageio_ffmpeg.get_ffmpeg_exe()


def duration(video):
    r = subprocess.run([FF, "-i", str(video)], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
    if not m:
        return 0.0
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def safe_stem(name):
    """ASCII安全なファイル名の幹を作る（日本語名・空白対策）。"""
    stem = pathlib.Path(name).stem
    s = re.sub(r"[^A-Za-z0-9_-]", "_", stem).strip("_")
    return s or "reel_draft"


def main():
    args = sys.argv[1:]
    language = "ja"
    if "--language" in args:
        language = args[args.index("--language") + 1]
    src = pathlib.Path(args[0]).expanduser()
    out = pathlib.Path(args[1])
    if not src.exists():
        print(f"動画が見つかりません: {src}", file=sys.stderr)
        sys.exit(1)
    data_dir = out / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. コピー ----------------------------------------------------------
    stem = safe_stem(src.name)
    dst = out / f"{stem}{src.suffix.lower()}"
    if not dst.exists():
        shutil.copy2(src, dst)
    print(f"[1/4] video -> {dst.name}", flush=True)

    # ---- 2. カバー抽出 ------------------------------------------------------
    cover = out / f"{stem}.jpg"
    if not cover.exists():
        subprocess.run(
            [FF, "-v", "error", "-ss", "0.1", "-i", str(dst),
             "-frames:v", "1", "-vf", "scale=480:-1", str(cover), "-y"],
            capture_output=True)
    print(f"[2/4] cover -> {cover.name if cover.exists() else '抽出失敗'}",
          flush=True)

    # ---- 3. メタ保存 --------------------------------------------------------
    dur = duration(dst)
    meta = {
        "source": "local_file",
        "original_path": str(src),
        "id": stem,
        "video_file": dst.name,
        "thumb_file": cover.name if cover.exists() else None,
        "duration": round(dur, 1),
        "downloaded": True,
        # URL入力と形式を揃える（ローカルファイルでは取れない項目はnull）
        "uploader": None, "caption": None,
        "like_count": None, "comment_count": None, "view_count": None,
    }
    json.dump(meta, open(data_dir / "meta.json", "w"),
              ensure_ascii=False, indent=1)
    print(f"[3/4] meta -> {data_dir/'meta.json'} (dur={dur:.1f}s)", flush=True)

    # ---- 4. 文字起こし ------------------------------------------------------
    txt_path = data_dir / "transcript.txt"
    if txt_path.exists() and txt_path.read_text(encoding="utf-8").strip():
        print("[4/4] 文字起こし済み（スキップ）", flush=True)
        print("done", flush=True)
        return
    print(f"[4/4] transcribing {dst.name} (backend: {BACKEND})", flush=True)
    try:
        full, segs, adur = transcribe_chunked(dst, language)
        txt_path.write_text(full, encoding="utf-8")
        (data_dir / "transcript.segments.json").write_text(
            json.dumps(segs, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"      OK: {full[:50]}... ({len(segs)}セグメント)", flush=True)
        warn = check_transcript(full, segs, adur)
        if warn:
            meta["transcript_warning"] = warn
            json.dump(meta, open(data_dir / "meta.json", "w"),
                      ensure_ascii=False, indent=1)
            print(f"      ⚠ 要確認: {warn}", flush=True)
    except Exception as e:
        txt_path.write_text("", encoding="utf-8")
        print(f"      FAILED: {e}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
