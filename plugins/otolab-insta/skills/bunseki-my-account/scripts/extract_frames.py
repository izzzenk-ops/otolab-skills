#!/usr/bin/env python3
"""インサイトの画面録画から「読むべきフレーム」を一定間隔で抜き出す。

受講生はスマホのインサイト画面を、各画面で1〜2秒止まりながらゆっくり
スクロールして撮る。そこから一定間隔（既定1.5秒ごと）で静止画を切り出せば、
維持率グラフ・リーチ内訳・視聴時間・アカウント全体データなど、読むべき画面が
ひと通り拾える（検証済み：2秒間隔でも維持率カーブまで読めた）。

使い方:
  python3 extract_frames.py <出力先ディレクトリ> <録画1.mp4> [<録画2.mp4> ...] [--every 1.5]

出力:
  <出力先>/<録画のファイル名(拡張子なし)>/f_001.jpg, f_002.jpg, ...
  <出力先>/frames_manifest.json  … 各録画のフレーム一覧

備考:
  - スマホ縦画面なので横540pxに縮小（数字が読める範囲でトークン節約）
  - 再実行しても安全（対象フォルダのフレームは作り直す）
"""
import json
import pathlib
import re
import subprocess
import sys


def extract(video: pathlib.Path, outdir: pathlib.Path, every: float):
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("f_*.jpg"):
        old.unlink()
    fps = 1.0 / every  # every秒ごとに1枚
    subprocess.run([
        "ffmpeg", "-v", "error", "-i", str(video),
        "-vf", f"fps={fps:.4f},scale=540:-1", "-q:v", "4",
        str(outdir / "f_%03d.jpg"),
    ], capture_output=True, text=True)
    return sorted(p.name for p in outdir.glob("f_*.jpg"))


def main():
    args = sys.argv[1:]
    every = 1.5
    if "--every" in args:
        i = args.index("--every")
        every = float(args[i + 1])
        del args[i:i + 2]
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)

    outroot = pathlib.Path(args[0])
    videos = [pathlib.Path(v) for v in args[1:]]
    outroot.mkdir(parents=True, exist_ok=True)

    manifest = {}
    for v in videos:
        if not v.exists():
            print(f"[SKIP] not found: {v}", flush=True)
            continue
        stem = re.sub(r"\W+", "_", v.stem).strip("_") or "rec"
        # 同名衝突を避ける
        base, n = stem, 2
        while stem in manifest:
            stem = f"{base}_{n}"
            n += 1
        sub = outroot / stem
        frames = extract(v, sub, every)
        manifest[stem] = {"video": str(v), "dir": str(sub), "frames": frames}
        print(f"[OK] {v.name} -> {len(frames)} frames in {sub}", flush=True)

    (outroot / "frames_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(m["frames"]) for m in manifest.values())
    print(f"done: {len(manifest)} recordings, {total} frames -> {outroot}")


if __name__ == "__main__":
    main()
