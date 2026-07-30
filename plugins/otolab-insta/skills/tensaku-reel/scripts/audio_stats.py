#!/usr/bin/env python3
"""音声の音量・無音区間を実測する（添削の「音声」評価と離脱リスク検出の根拠用）。

  <venv>/bin/python audio_stats.py <video> <out_json> [--silence-db -35] [--min-silence 1.0]

ffmpeg（imageio-ffmpeg同梱・OS非依存）の volumedetect / silencedetect で:
  - mean_volume_db / max_volume_db  … 全体の音量（-30dBより小さい mean は音量不足の疑い）
  - silences[]                       … <min-silence>秒以上の無音区間（start/end/duration）

注意: 無音検出はBGM込みの判定。BGMが常時鳴っているリールでは無音は出ない。
その場合「話者の間」は transcript.segments.json のギャップで見ること。
"""
import json
import pathlib
import re
import subprocess
import sys

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()


def main():
    args = sys.argv[1:]
    video = pathlib.Path(args[0])
    out_json = pathlib.Path(args[1])
    silence_db = args[args.index("--silence-db") + 1] if "--silence-db" in args else "-35"
    min_sil = args[args.index("--min-silence") + 1] if "--min-silence" in args else "1.0"

    r = subprocess.run(
        [FF, "-i", str(video),
         "-af", f"volumedetect,silencedetect=noise={silence_db}dB:d={min_sil}",
         "-f", "null", "-"],
        capture_output=True, text=True)
    log = r.stderr

    stats = {"video": video.name,
             "silence_threshold_db": float(silence_db),
             "min_silence_sec": float(min_sil)}

    m = re.search(r"mean_volume:\s*(-?[\d.]+)\s*dB", log)
    stats["mean_volume_db"] = float(m.group(1)) if m else None
    m = re.search(r"max_volume:\s*(-?[\d.]+)\s*dB", log)
    stats["max_volume_db"] = float(m.group(1)) if m else None
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", log)
    if m:
        h, mi, s = m.groups()
        stats["duration"] = round(int(h) * 3600 + int(mi) * 60 + float(s), 1)

    silences = []
    starts = re.findall(r"silence_start:\s*(-?[\d.]+)", log)
    ends = re.findall(r"silence_end:\s*(-?[\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)", log)
    for i, st in enumerate(starts):
        if i < len(ends):
            silences.append({"start": round(float(st), 1),
                             "end": round(float(ends[i][0]), 1),
                             "duration": round(float(ends[i][1]), 1)})
        else:                                   # 末尾まで無音のまま終了
            silences.append({"start": round(float(st), 1),
                             "end": stats.get("duration"),
                             "duration": None})
    stats["silences"] = silences

    out_json.parent.mkdir(parents=True, exist_ok=True)
    json.dump(stats, open(out_json, "w"), ensure_ascii=False, indent=1)
    print(f"mean={stats['mean_volume_db']}dB max={stats['max_volume_db']}dB "
          f"silences={len(silences)} -> {out_json}")
    for s in silences:
        print(f"  {s['start']}s - {s['end']}s ({s['duration']}s)")


if __name__ == "__main__":
    main()
