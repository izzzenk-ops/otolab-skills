#!/usr/bin/env python3
"""frames.js（文面の各枚）を 1080x1920 のストーリー画像に書き出す。Mac / Windows 両対応。

使い方:
  python3 render.py <frames.jsのパス> [出力フォルダ] [--draft]
    出力フォルダを省略すると frames.js と同じ場所の png/ に出す
    --draft を付けると、スタンプを置く位置に点線の目印が入る（確認用。投稿には使わない）

出力: png/01.png … と、全部の枚を並べた png/一覧.png
依存: Google Chrome か Microsoft Edge だけ（Pythonの標準ライブラリのみ）
"""
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_browser():
    cands = []
    sysname = platform.system()
    if sysname == "Darwin":
        cands += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    elif sysname == "Windows":
        for base in [os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                     os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                     os.environ.get("LOCALAPPDATA", "")]:
            if base:
                cands += [os.path.join(base, r"Google\Chrome\Application\chrome.exe"),
                          os.path.join(base, r"Microsoft\Edge\Application\msedge.exe")]
    for name in ["google-chrome", "chromium", "chromium-browser", "chrome", "msedge"]:
        p = shutil.which(name)
        if p:
            cands.append(p)
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


def run(browser, args, timeout=90):
    base = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--force-device-scale-factor=1", "--allow-file-access-from-files",
            "--virtual-time-budget=6000"]
    try:
        return subprocess.run(base + args, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        print("エラー: ブラウザの書き出しが時間内に終わりませんでした。開いているChromeを一度閉じてから、もう一度実行してください。")
        sys.exit(1)


def convert_heic(frames: Path):
    """frames.js の中の .heic 写真を jpg に直す（Chromeは HEIC を表示できない）"""
    text = frames.read_text(encoding="utf-8")
    heics = sorted(set(re.findall(r"['\"]([^'\"]+\.(?:heic|HEIC))['\"]", text)))
    if not heics:
        return
    changed = False
    for h in heics:
        src = (frames.parent / h) if not os.path.isabs(h) else Path(h)
        dst = src.with_suffix(".jpg")
        if not dst.exists():
            if platform.system() == "Darwin":
                subprocess.run(["sips", "-s", "format", "jpeg", str(src), "--out", str(dst)], capture_output=True)
                if not dst.exists():
                    print(f"エラー: {src.name} をjpgに変換できませんでした。写真アプリからjpgで書き出してください。")
                    sys.exit(1)
            else:
                print(f"エラー: {src.name} はHEIC形式です。Windowsでは自動で変換できません。"
                      "iPhoneの設定（カメラ → フォーマット →「互換性優先」）にするか、jpgで保存し直してから、もう一度実行してください。")
                sys.exit(1)
        text = text.replace(h, str(Path(h).with_suffix(".jpg")).replace("\\", "/"))
        changed = True
    if changed:
        frames.write_text(text, encoding="utf-8")
        print("HEICの写真をjpgに変換して、frames.js を書き換えました")


def check_photos(frames: Path):
    """frames.js に書かれた写真が実際にあるかを先に確かめる（無いと黙って無地になるため）"""
    text = frames.read_text(encoding="utf-8")
    paths = re.findall(r"photo\s*:\s*['\"]([^'\"]+)['\"]", text)
    paths += re.findall(r"\[\s*['\"]card['\"]\s*,\s*['\"]([^'\"]+)['\"]", text)
    missing = []
    for p in paths:
        if re.match(r"^(https?|file):", p):
            continue
        q = Path(p) if (os.path.isabs(p) or re.match(r"^[A-Za-z]:[\\/]", p)) else frames.parent / p
        if not q.exists():
            missing.append(p)
    if missing:
        print("エラー: 次の写真が見つかりません。場所かファイル名を確かめてください。")
        for p in missing:
            print("  - " + p)
        sys.exit(1)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    draft = "--draft" in sys.argv
    if not args:
        print(__doc__)
        sys.exit(1)
    frames = Path(args[0]).resolve()
    if not frames.exists():
        print(f"エラー: {frames} が見つかりません。frames.js の場所を確かめてください。")
        sys.exit(1)
    out = Path(args[1]).resolve() if len(args) > 1 else frames.parent / "png"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("[0-9][0-9].png"):
        old.unlink()  # 前回の枚が残って混ざらないように
    browser = find_browser()
    if not browser:
        print("エラー: Google Chrome（または Microsoft Edge）が見つかりません。Chromeを入れてから、もう一度実行してください。")
        sys.exit(1)
    convert_heic(frames)
    check_photos(frames)

    tpl = (HERE / "story.html").as_uri()
    set_url = frames.as_uri()
    # 枚数を数える（f=0 のとき story.html が <title> に枚数を書く）
    r = run(browser, ["--dump-dom", f"{tpl}?set={set_url}&f=0"])
    m = re.search(r"<title>(\d+)</title>", r.stdout)
    if not m or m.group(1) == "0":
        print("エラー: frames.js を読めませんでした。書き方の誤り（カンマ抜け・かっこの閉じ忘れ）がないか確認してください。")
        print("\n".join(l for l in r.stderr.splitlines() if "ERROR:" not in l and "WARNING:" not in l and "allocator" not in l)[-400:])
        sys.exit(1)
    n = int(m.group(1))

    # 点検：文字のはみ出し・読めない写真
    warns = []
    for i in range(1, n + 1):
        r = run(browser, ["--dump-dom", f"{tpl}?set={set_url}&f={i}&check=1"])
        m = re.search(r"CHECK over=(\d+) badimg=(\d+)", r.stdout)
        if m and int(m.group(1)) > 0:
            warns.append(f"{i}枚目：文字が下の空き（返信欄の上）に{m.group(1)}pxはみ出しています。文字を減らすか、top を上げるか、fs を下げてください")
        if m and int(m.group(2)) > 0:
            warns.append(f"{i}枚目：表示できない写真があります（壊れたファイル・HEIC・対応していない形式）")

    pngs = []
    for i in range(1, n + 1):
        png = out / f"{i:02d}.png"
        url = f"{tpl}?set={set_url}&f={i}" + ("&draft=1" if draft else "")
        if png.exists():
            png.unlink()
        run(browser, ["--window-size=1080,1920", f"--screenshot={png}", url])
        if not png.exists():
            print(f"失敗: {i}枚目")
            sys.exit(1)
        pngs.append(png)
        print(f"OK  {png.name}")

    # 一覧（配分と見た目のばらつきを確認するため）
    cols = min(8, n)
    rows = (n + cols - 1) // cols
    w, h = 300, 533
    html = ["<html><body style='margin:0;background:#fff;display:grid;gap:10px;padding:10px;",
            f"grid-template-columns:repeat({cols},{w}px)'>"]
    for i, p in enumerate(pngs, 1):
        html.append(f"<div style='font:20px sans-serif;text-align:center'><img src='{p.as_uri()}' style='width:{w}px;height:{h}px;display:block'>{i}</div>")
    html.append("</body></html>")
    tmp = Path(tempfile.gettempdir()) / "stories_overview.html"
    tmp.write_text("".join(html), encoding="utf-8")
    run(browser, [f"--window-size={cols*(w+10)+10},{rows*(h+40)+20}", f"--screenshot={out/'一覧.png'}", tmp.as_uri()])
    print(f"\n完了: {n}枚 → {out}")
    print(f"一覧: {out/'一覧.png'}")
    if warns:
        print("\n⚠️ 直したほうがいいところ:")
        for w_ in warns:
            print("  - " + w_)


if __name__ == "__main__":
    main()
