#!/usr/bin/env python3
"""テロップ主体アカウント用：動画からフレームを抜き、読みやすいグリッド画像を作る。

使い方:
  python3 telop_frames.py <selection.json | id1,id2,...> <reels_dir> <out_dir> [--every 4] [--cols 4]

各動画を every 秒ごとにサンプリングし、ffmpeg の tile フィルタで1枚のグリッド画像
（out_dir/grid_<id>.jpg）にまとめる。モデルはこの画像をReadして画面テロップを実読する。

依存は ffmpeg/ffprobe のみ（setup.sh で導入済み）。PIL不要＝受講生環境でも動く。
音声はBGMで使えないアカウント（detect_narration.py が telop_driven と判定）で使う。
"""
import json
import math
import os
import pathlib
import subprocess
import sys


def duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def make_grid(video, out, every, cols):
    dur = duration(video)
    if dur <= 0:
        return False, "尺取得失敗"
    nframes = max(1, math.ceil(dur / every))
    rows = max(1, math.ceil(nframes / cols))
    # fps=1/every で等間隔サンプリング → scale → tile で1枚に
    vf = f"fps=1/{every},scale=380:-1,tile={cols}x{rows}"
    r = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
         "-vf", vf, "-frames:v", "1", "-q:v", "3", str(out)],
        capture_output=True, text=True)
    ok = r.returncode == 0 and pathlib.Path(out).exists()
    return ok, (r.stderr.strip()[-200:] if not ok else f"{nframes}枚/{cols}x{rows}")


def resolve_ids(arg, reels_dir):
    p = pathlib.Path(arg)
    if p.exists() and p.suffix == ".json":
        sel = json.load(open(p))
        return [it["id"] for it in sel]
    return [x for x in arg.split(",") if x]


def main():
    args = sys.argv[1:]
    every, cols = 4, 4
    if "--every" in args:
        every = int(args[args.index("--every") + 1])
    if "--cols" in args:
        cols = int(args[args.index("--cols") + 1])
    ids = resolve_ids(args[0], args[1])
    reels_dir = pathlib.Path(args[1])
    out_dir = pathlib.Path(args[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    grids = []
    for rid in ids:
        v = reels_dir / f"{rid}.mp4"
        if not v.exists():
            print(f"  SKIP {rid}: mp4なし")
            continue
        out = out_dir / f"grid_{rid}.jpg"
        ok, info = make_grid(v, out, every, cols)
        print(f"  {'OK  ' if ok else 'FAIL'} {rid}: {info}")
        if ok:
            grids.append(str(out))
    print(f"\n{len(grids)}本のグリッド完成 -> {out_dir}")
    print("次: これらの画像をReadして、各フレームの白テロップを時系列で書き起こす")
    for g in grids:
        print("  Read:", g)


if __name__ == "__main__":
    main()
