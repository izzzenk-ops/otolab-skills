#!/usr/bin/env python3
"""1本のリールURLを丸ごと取り込む（メタ情報・動画・サムネ・文字起こし）。

setup.py が作った venv の python で実行すること（yt-dlp・faster/mlx whisper・
imageio-ffmpeg が入っている）:
  <venv>/bin/python fetch_reel.py <reel_url> <out_dir> [--language ja]   (Mac/Linux)
  <venv>\\Scripts\\python.exe fetch_reel.py <reel_url> <out_dir>          (Windows)

動作:
  1. yt-dlp（venvモジュール）で動画(mp4)・カバー画像(jpg)・メタ(info.json)を取得
     - まずcookieなし → 失敗したら --cookies-from-browser chrome で再試行
  2. info.json から使う項目を整形して <out_dir>/data/meta.json に保存
  3. 音声を文字起こし → <out_dir>/data/transcript.txt（全文）と
     transcript.segments.json（タイムスタンプ付き）。バックエンドは
     transcribe_core が自動選択（Apple Silicon=mlx / それ以外=faster-whisper）

済みファイルはスキップ。動画DLに失敗してもメタ取得だけは試みる。OS非依存。
"""
import json
import pathlib
import re
import subprocess
import sys

from transcribe_core import BACKEND, check_transcript, transcribe_chunked


def run_ytdlp(url, outdir, use_cookies):
    # venv内のyt-dlpをモジュールとして呼ぶ（OS非依存・PATHにyt-dlp不要）
    cmd = [sys.executable, "-m", "yt_dlp",
           "-o", f"{outdir}/%(id)s.%(ext)s",
           "--write-thumbnail", "--convert-thumbnails", "jpg",
           "--write-info-json",
           "--no-playlist",
           "-f", "mp4/best",
           "--no-progress",
           url]
    if use_cookies:
        cmd[3:3] = ["--cookies-from-browser", "chrome"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return r.returncode == 0, (r.stderr or "").strip()[-500:]
    except subprocess.TimeoutExpired:
        return False, "timeout (300s)"


def shorten_id(url):
    m = re.search(r"/reel[s]?/([^/?#]+)", url)
    return m.group(1) if m else "reel"


def main():
    args = sys.argv[1:]
    language = "ja"
    if "--language" in args:
        language = args[args.index("--language") + 1]
    url = args[0]
    out = pathlib.Path(args[1])
    data_dir = out / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. yt-dlp 取得 -----------------------------------------------------
    print(f"[1/3] yt-dlp downloading {url}", flush=True)
    ok, err = run_ytdlp(url, out, use_cookies=False)
    if not ok:
        print("      cookieなし失敗 → chromeのcookieで再試行", flush=True)
        ok, err = run_ytdlp(url, out, use_cookies=True)
    if not ok:
        print(f"      DL失敗: {err.splitlines()[-1] if err else 'unknown'}",
              flush=True)

    # ---- 2. メタ整形 --------------------------------------------------------
    info_files = sorted(out.glob("*.info.json"))
    meta = {"url": url, "downloaded": ok}
    if info_files:
        raw = json.load(open(info_files[0], encoding="utf-8"))
        meta.update({
            "id": raw.get("id") or shorten_id(url),
            "uploader": raw.get("uploader") or raw.get("channel"),
            "uploader_id": raw.get("uploader_id"),
            "caption": (raw.get("description") or "").strip(),
            "like_count": raw.get("like_count"),
            "comment_count": raw.get("comment_count"),
            "view_count": raw.get("view_count"),
            "duration": raw.get("duration"),
            "upload_date": raw.get("upload_date"),
            "title": (raw.get("title") or "").strip(),
        })
    else:
        meta["id"] = shorten_id(url)
        print("      info.jsonが無い（メタ取得できず）", flush=True)

    mp4s = sorted(out.glob("*.mp4"))
    jpgs = sorted(out.glob("*.jpg"))
    meta["video_file"] = mp4s[0].name if mp4s else None
    meta["thumb_file"] = jpgs[0].name if jpgs else None
    json.dump(meta, open(data_dir / "meta.json", "w"),
              ensure_ascii=False, indent=1)
    print(f"[2/3] meta -> {data_dir/'meta.json'} "
          f"(likes={meta.get('like_count')} comments={meta.get('comment_count')} "
          f"views={meta.get('view_count')} dur={meta.get('duration')}s)", flush=True)

    # ---- 3. 文字起こし ------------------------------------------------------
    txt_path = data_dir / "transcript.txt"
    if not mp4s:
        print("[3/3] 動画が無いため文字起こしをスキップ", flush=True)
        txt_path.write_text("", encoding="utf-8")
        print("done (no video)", flush=True)
        return
    if txt_path.exists() and txt_path.read_text(encoding="utf-8").strip():
        print("[3/3] 文字起こし済み（スキップ）", flush=True)
        print("done", flush=True)
        return
    v = mp4s[0]
    print(f"[3/3] transcribing {v.name} (backend: {BACKEND})", flush=True)
    try:
        full, segs, dur = transcribe_chunked(v, language)
        txt_path.write_text(full, encoding="utf-8")
        (data_dir / "transcript.segments.json").write_text(
            json.dumps(segs, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"      OK: {full[:50]}... ({len(segs)}セグメント)", flush=True)
        warn = check_transcript(full, segs, dur)
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
