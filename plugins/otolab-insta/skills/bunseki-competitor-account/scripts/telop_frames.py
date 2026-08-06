#!/usr/bin/env python3
"""テロップ主体アカウント用：動画からフレームを抜き、画面テロップを実読できる画像を作る。

使い方:
  python3 telop_frames.py <selection.json | id1,id2,...> <reels_dir> <out_dir> [--every 2] [--grid] [--cols 4]

各動画を every 秒ごとにサンプリングし、1枚ずつ out_dir/<id>_NN.jpg（幅540px）で書き出す。
モデルはこの1枚1枚をReadして白テロップを時系列で書き起こす。
グリッド1枚に詰めると日本語テロップが潰れて読めないので、既定は個別フレーム。
--grid を付けたときだけ俯瞰用の out_dir/grid_<id>.jpg も作る（構成のあたりを付ける用途）。

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


def make_frames(video, out_dir, rid, every):
    """every秒ごとに1枚ずつ書き出す。戻り値は生成されたパスのリスト。"""
    for old in out_dir.glob(f"{rid}_[0-9][0-9].jpg"):
        old.unlink()
    pattern = str(out_dir / f"{rid}_%02d.jpg")
    r = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
         "-vf", f"fps=1/{every},scale=540:-2", "-q:v", "3", pattern],
        capture_output=True, text=True)
    frames = sorted(out_dir.glob(f"{rid}_[0-9][0-9].jpg"))
    if not frames:
        return [], r.stderr.strip()[-200:] or "フレーム抽出失敗"
    return frames, f"{len(frames)}枚"


def make_grid(video, out, every, cols):
    dur = duration(video)
    if dur <= 0:
        return False, "尺取得失敗"
    nframes = max(1, math.ceil(dur / every))
    rows = max(1, math.ceil(nframes / cols))
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
    every, cols = 2, 4
    want_grid = "--grid" in args
    if "--every" in args:
        every = int(args[args.index("--every") + 1])
    if "--cols" in args:
        cols = int(args[args.index("--cols") + 1])
    ids = resolve_ids(args[0], args[1])
    reels_dir = pathlib.Path(args[1])
    out_dir = pathlib.Path(args[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    tr_dir = reels_dir / "transcripts"

    done = []
    for rid in ids:
        v = reels_dir / f"{rid}.mp4"
        if not v.exists():
            print(f"  SKIP {rid}: mp4なし")
            continue
        frames, info = make_frames(v, out_dir, rid, every)
        print(f"  {'OK  ' if frames else 'FAIL'} {rid}: {info}")
        if want_grid:
            ok, ginfo = make_grid(v, out_dir / f"grid_{rid}.jpg", every * 2, cols)
            print(f"       grid: {'OK' if ok else 'FAIL'} {ginfo}")
        if frames:
            done.append((rid, frames))

    total = sum(len(f) for _, f in done)
    print(f"\n{len(done)}本 / 計{total}枚のフレーム -> {out_dir}")
    print("次の手順（1本ずつ最後までやり切ること。まとめて読もうとしない）:")
    print(f"  1. 1本ぶんのフレームを全部Readして、白テロップを時系列で書き起こす")
    print(f"  2. その1本を {tr_dir}/<ID>.telop.txt に即保存する（次の本に進む前に保存する）")
    print(f"  3. 全{len(done)}本ぶん繰り返す。報告書のtr-boxはこの .telop.txt から作る")
    print("\n対象（この順に処理する）:")
    for rid, frames in done:
        print(f"  {rid}: {len(frames)}枚  {frames[0].name} 〜 {frames[-1].name}")


if __name__ == "__main__":
    main()
