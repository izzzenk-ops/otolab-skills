#!/usr/bin/env python3
"""selection.json のリール動画をyt-dlpでダウンロードする（カバー画像付き）。

使い方:
  python3 download_reels.py <selection.json> <output_dir>

動作:
  - まずcookieなしで試行、失敗したら --cookies-from-browser chrome で再試行
  - 動画は <output_dir>/<リールID>.mp4、カバー画像は <リールID>.jpg
  - 各ダウンロード間に3秒待つ（レート制限・BAN回避のため間隔は詰めない）
  - 結果を <output_dir>/download_log.json に保存。失敗してもスキップして続行する
"""
import json
import pathlib
import subprocess
import sys
import time


def run_ytdlp(url, outdir, use_cookies):
    cmd = ["yt-dlp",
           "-o", f"{outdir}/%(id)s.%(ext)s",
           "--write-thumbnail", "--convert-thumbnails", "jpg",
           "--no-playlist",
           "-f", "mp4/best",
           "--no-progress",
           url]
    if use_cookies:
        cmd[1:1] = ["--cookies-from-browser", "chrome"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return r.returncode == 0, (r.stderr or "").strip()[-400:]
    except subprocess.TimeoutExpired:
        return False, "timeout (300s)"


def main():
    sel_path, outdir = sys.argv[1], sys.argv[2]
    pathlib.Path(outdir).mkdir(parents=True, exist_ok=True)
    items = json.load(open(sel_path))
    log = []
    for i, it in enumerate(items):
        url = it["url"]
        ok, err = run_ytdlp(url, outdir, use_cookies=False)
        if not ok:
            ok, err = run_ytdlp(url, outdir, use_cookies=True)
        log.append({"url": url, "id": it.get("id"), "downloaded": ok,
                    "error": None if ok else err})
        print(f"[{i + 1}/{len(items)}] {'OK    ' if ok else 'FAILED'} {url}",
              flush=True)
        if not ok:
            print(f"    -> {err.splitlines()[-1] if err else 'unknown error'}",
                  flush=True)
        time.sleep(3)
    json.dump(log, open(f"{outdir}/download_log.json", "w"),
              ensure_ascii=False, indent=1)
    ok_n = sum(1 for e in log if e["downloaded"])
    print(f"done: {ok_n}/{len(items)} downloaded -> {outdir}")


if __name__ == "__main__":
    main()
