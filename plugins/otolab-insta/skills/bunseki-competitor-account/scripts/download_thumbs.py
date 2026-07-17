#!/usr/bin/env python3
"""リール一覧JSONの全投稿のサムネイル（カバー画像）をyt-dlpで保存する。

使い方:
  python3 download_thumbs.py <reels.json> <output_dir> [--limit 60] [--exclude <selection.json>]

InstagramのCDNサムネURLは署名付きでツール経由で持ち出せないため、
yt-dlpの --skip-download --write-thumbnail で各リールのカバー画像だけを取得する。
--exclude に selection.json を渡すと、動画DL側でカバー画像を取得済みのリールを
スキップできる（APIヒット数の節約）。
保存名は <グリッド順3桁>_<リールID>.jpg（例: 001_DAbCdEf.jpg）。
"""
import json
import pathlib
import re
import subprocess
import sys
import time


def reel_id(url):
    m = re.search(r"/(?:reel|p)/([^/?]+)", url)
    return m.group(1) if m else re.sub(r"\W+", "_", url)[-20:]


def main():
    args = sys.argv[1:]
    limit = None
    exclude_ids = set()
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    if "--exclude" in args:
        sel = json.load(open(args[args.index("--exclude") + 1]))
        exclude_ids = {it["id"] for it in sel}
    data = json.load(open(args[0]))
    outdir = pathlib.Path(args[1])
    outdir.mkdir(parents=True, exist_ok=True)

    items = list(data.keys())
    if limit:
        items = items[:limit]
    ok = skipped = 0
    for i, url in enumerate(items):
        rid = reel_id(url)
        if rid in exclude_ids:
            skipped += 1
            continue
        cmd = ["yt-dlp", "--skip-download", "--write-thumbnail",
               "--convert-thumbnails", "jpg", "--no-playlist", "--no-progress",
               "-o", f"{outdir}/{i:03d}_{rid}.%(ext)s", url.split("?")[0]]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                ok += 1
            else:
                print(f"[{i:03d}] FAILED {rid}: "
                      f"{(r.stderr or '').strip().splitlines()[-1][:120]}",
                      flush=True)
        except subprocess.TimeoutExpired:
            print(f"[{i:03d}] FAILED {rid}: timeout", flush=True)
        time.sleep(2)
    print(f"done: {ok} thumbnails saved, {skipped} skipped (already have cover) "
          f"-> {outdir}")


if __name__ == "__main__":
    main()
