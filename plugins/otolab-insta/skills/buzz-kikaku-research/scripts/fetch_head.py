#!/usr/bin/env python3
"""リール1本の「冒頭だけ」を取り込む（動画DL・メタ・冒頭フレーム・冒頭文字起こし）。

buzz-kikaku-research は冒頭7秒しか分析しないので、bunseki-reel の fetch_reel.py より
ずっと軽い。setup.py が作った venv の python で実行すること:
  <venv>/bin/python fetch_head.py <reel_url> <out_dir> [--language ja]   (Mac/Linux)
  <venv>\\Scripts\\python.exe fetch_head.py <reel_url> <out_dir>          (Windows)

動作:
  1. yt-dlp で動画(mp4)・カバー(jpg)・メタ(info.json)を取得
     - まずcookieなし → 失敗したら --cookies-from-browser chrome で再試行
  2. info.json を整形して <out_dir>/data/meta.json に保存
  3. 冒頭フレームを抽出 → <out_dir>/frames/f_00.3s.jpg 等（0.3/1/2/3/5/7秒・幅360px）
  4. 冒頭12秒だけ文字起こし → <out_dir>/data/head_transcript.txt / .segments.json
     （フックのワード確認用。全文文字起こしはしない）

済みファイルはスキップ。動画DLに失敗してもメタ取得だけは試みる。OS非依存。
"""
import json
import pathlib
import re
import subprocess
import sys

from transcribe_core import (BACKEND, SR, _transcribe_faster, _transcribe_mlx,
                             check_transcript, decode_audio)

HEAD_SECONDS = 12.0                       # 文字起こしする冒頭の長さ
FRAME_TIMES = [0.3, 1.0, 2.0, 3.0, 5.0, 7.0]   # 冒頭フレームの抽出位置(秒)


def run_ytdlp(url, outdir, use_cookies):
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


def extract_head_frames(video, out, width=360):
    """冒頭の固定タイムスタンプでフレームを抜く（imageio-ffmpeg同梱バイナリ・OS非依存）。"""
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([ff, "-i", str(video)], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
    dur = 0.0
    if m:
        h, mi, s = m.groups()
        dur = int(h) * 3600 + int(mi) * 60 + float(s)
    made = []
    for t in FRAME_TIMES:
        if dur and t >= dur - 0.2:
            break
        name = f"f_{t:04.1f}s.jpg"
        p = out / name
        if not p.exists():
            subprocess.run(
                [ff, "-v", "error", "-ss", f"{t:.2f}", "-i", str(video),
                 "-frames:v", "1", "-vf", f"scale={width}:-1", str(p), "-y"],
                capture_output=True)
        if p.exists():
            made.append(name)
    return made, dur


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
    print(f"[1/4] yt-dlp downloading {url}", flush=True)
    mp4s = sorted(out.glob("*.mp4"))
    if mp4s:
        print("      動画取得済み（スキップ）", flush=True)
        ok = True
    else:
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
    print(f"[2/4] meta -> {data_dir/'meta.json'} "
          f"(views={meta.get('view_count')} likes={meta.get('like_count')} "
          f"dur={meta.get('duration')}s)", flush=True)

    if not mp4s:
        print("[3/4][4/4] 動画が無いためフレーム・文字起こしをスキップ", flush=True)
        (data_dir / "head_transcript.txt").write_text("", encoding="utf-8")
        print("done (no video)", flush=True)
        return
    v = mp4s[0]

    # ---- 3. 冒頭フレーム ----------------------------------------------------
    made, dur = extract_head_frames(v, out / "frames")
    print(f"[3/4] frames ({len(made)}枚) -> {out/'frames'}", flush=True)
    for n in made:
        print(f"      {n}", flush=True)

    # ---- 4. 冒頭だけ文字起こし ----------------------------------------------
    txt_path = data_dir / "head_transcript.txt"
    if txt_path.exists() and txt_path.read_text(encoding="utf-8").strip():
        print("[4/4] 文字起こし済み（スキップ）", flush=True)
        print("done", flush=True)
        return
    print(f"[4/4] transcribing head {HEAD_SECONDS:.0f}s of {v.name} "
          f"(backend: {BACKEND})", flush=True)
    try:
        audio = decode_audio(v)[: int(HEAD_SECONDS * SR)]
        if BACKEND == "mlx":
            full, segs, _ = _transcribe_mlx(audio, language)
        else:
            full, segs, _ = _transcribe_faster(audio, language)
        txt_path.write_text(full, encoding="utf-8")
        (data_dir / "head_transcript.segments.json").write_text(
            json.dumps(segs, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"      OK: {full[:60]}", flush=True)
        warn = check_transcript(full, segs, min(HEAD_SECONDS, dur or HEAD_SECONDS))
        if warn:
            meta["head_transcript_warning"] = warn
            json.dump(meta, open(data_dir / "meta.json", "w"),
                      ensure_ascii=False, indent=1)
            print(f"      ⚠ 要確認: {warn}（冒頭がBGMのみの可能性。フレームで裏取り）",
                  flush=True)
    except Exception as e:
        txt_path.write_text("", encoding="utf-8")
        print(f"      FAILED: {e}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
