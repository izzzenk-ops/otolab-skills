#!/usr/bin/env python3
"""リール動画から等間隔でフレームを抜き出す（テロップ・演出・サムネ帯の分析用）。

<venv>/bin/python extract_frames.py <video> <out_dir> [--count 12] [--width 360]

- ffmpeg は imageio-ffmpeg 同梱バイナリを使う（Mac/Windows/Linux 非依存・PATH不要）
- 動画尺を測り、等間隔に <count> 枚を抽出（各フレームを -ss でシーク）
- ファイル名にタイムスタンプを埋める: f_03.5s.jpg（＝3.5秒地点）
  → Claudeが読むときテロップの時系列を復元できる
- 幅を <width>px に縮小（読み取り用・トークン節約）

音声ナレーションが無い（BGMのみ）リールでは文字起こしが空/幻覚になる。
その場合この抽出フレームのテロップが実質の「台本」になる。
"""
import pathlib
import re
import subprocess
import sys

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()


def duration(video):
    """ffmpegの標準エラー出力から尺(秒)を得る（ffprobe不要・OS非依存）。"""
    r = subprocess.run([FF, "-i", str(video)], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
    if not m:
        return 0.0
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def main():
    args = sys.argv[1:]
    video = pathlib.Path(args[0])
    out = pathlib.Path(args[1])
    count = int(args[args.index("--count") + 1]) if "--count" in args else 12
    width = int(args[args.index("--width") + 1]) if "--width" in args else 360
    out.mkdir(parents=True, exist_ok=True)

    dur = duration(video)
    if dur <= 0:
        print("尺が取得できませんでした", file=sys.stderr)
        sys.exit(1)

    margin = min(0.6, dur * 0.03)          # 先頭・末尾の黒/切替フレームを避ける
    span = dur - margin * 2
    made = []
    for i in range(count):
        t = margin + span * i / max(count - 1, 1)
        name = f"f_{t:05.1f}s.jpg"
        p = out / name
        subprocess.run(
            [FF, "-v", "error", "-ss", f"{t:.2f}", "-i", str(video),
             "-frames:v", "1", "-vf", f"scale={width}:-1", str(p), "-y"],
            capture_output=True)
        if p.exists():
            made.append(name)
    print(f"duration={dur:.1f}s / extracted {len(made)} frames -> {out}")
    for n in made:
        print(f"  {n}")


if __name__ == "__main__":
    main()
