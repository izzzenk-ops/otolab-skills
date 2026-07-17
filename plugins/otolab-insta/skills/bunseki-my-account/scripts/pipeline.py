#!/usr/bin/env python3
"""動画ダウンロードと文字起こしを並行実行するパイプライン（時間をほぼ半分にする）。

必ず文字起こしライブラリが入ったvenvのpythonで実行すること:
  Mac    : ~/telop-tool/venv/bin/python3    pipeline.py <selection.json> <reels_dir> [--language ja]
  Windows: ~/telop-tool/venv/Scripts/python.exe pipeline.py <selection.json> <reels_dir> [--language ja]

文字起こしエンジンはOSで自動的に切り替わる（transcribe_engine.py）:
  Mac(Apple Silicon)=mlx_whisper ／ Windows など=faster-whisper

動作:
  - 別スレッド: yt-dlpで順次ダウンロード（2秒間隔、cookieなし→失敗時chromeのcookieで再試行）
  - メインスレッド: mp4が届くたびに文字起こし（Whisperモデルのロードは1回だけ）
  - 出力は download_reels.py + transcribe.py と同一（download_log.json / transcripts/）
  - 済みファイルはスキップするので再実行しても安全
"""
import json
import pathlib
import subprocess
import sys
import threading
import time

from transcribe_engine import transcribe_file


def run_ytdlp(url, outdir, use_cookies):
    cmd = ["yt-dlp", "-o", f"{outdir}/%(id)s.%(ext)s",
           "--write-thumbnail", "--convert-thumbnails", "jpg",
           "--no-playlist", "-f", "mp4/best", "--no-progress", url]
    if use_cookies:
        cmd[1:1] = ["--cookies-from-browser", "chrome"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return r.returncode == 0, (r.stderr or "").strip()[-400:]
    except subprocess.TimeoutExpired:
        return False, "timeout (300s)"


def downloader(items, outdir, state):
    log = []
    for i, it in enumerate(items):
        url, rid = it["url"], it.get("id")
        if (outdir / f"{rid}.mp4").exists():
            print(f"[DL {i + 1}/{len(items)}] SKIP (exists) {rid}", flush=True)
            log.append({"url": url, "id": rid, "downloaded": True, "error": None})
            continue
        ok, err = run_ytdlp(url, outdir, use_cookies=False)
        if not ok:
            ok, err = run_ytdlp(url, outdir, use_cookies=True)
        log.append({"url": url, "id": rid, "downloaded": ok,
                    "error": None if ok else err})
        print(f"[DL {i + 1}/{len(items)}] {'OK    ' if ok else 'FAILED'} {url}",
              flush=True)
        time.sleep(2)
    json.dump(log, open(outdir / "download_log.json", "w"),
              ensure_ascii=False, indent=1)
    state["dl_done"] = True
    ok_n = sum(1 for e in log if e["downloaded"])
    print(f"[DL] done: {ok_n}/{len(items)}", flush=True)


def main():
    args = sys.argv[1:]
    language = "ja"
    if "--language" in args:
        language = args[args.index("--language") + 1]
    items = json.load(open(args[0]))
    outdir = pathlib.Path(args[1])
    outdir.mkdir(parents=True, exist_ok=True)
    tdir = outdir / "transcripts"
    tdir.mkdir(exist_ok=True)

    state = {"dl_done": False}
    t = threading.Thread(target=downloader, args=(items, outdir, state),
                         daemon=True)
    t.start()

    done = 0
    while True:
        pending = [v for v in sorted(outdir.glob("*.mp4"))
                   if not (tdir / f"{v.stem}.txt").exists()]
        if not pending:
            if state["dl_done"]:
                break
            time.sleep(2)
            continue
        v = pending[0]
        # 書き込み途中のファイルを掴まないよう、サイズが安定するまで待つ
        size = -1
        while v.stat().st_size != size:
            size = v.stat().st_size
            time.sleep(1)
        try:
            text, segs = transcribe_file(str(v), language)
            (tdir / f"{v.stem}.txt").write_text(text, encoding="utf-8")
            (tdir / f"{v.stem}.segments.json").write_text(
                json.dumps(segs, ensure_ascii=False, indent=1),
                encoding="utf-8")
            done += 1
            head = text[:40].replace("\n", " ")
            print(f"[TR {done}] OK {v.name}: {head}...", flush=True)
        except Exception as e:
            # 失敗マーカーを置いて無限ループを防ぐ
            (tdir / f"{v.stem}.txt").write_text("", encoding="utf-8")
            print(f"[TR] FAILED {v.name}: {e}", flush=True)

    t.join(timeout=10)
    print(f"pipeline done: {done} transcribed -> {tdir}", flush=True)


if __name__ == "__main__":
    main()
