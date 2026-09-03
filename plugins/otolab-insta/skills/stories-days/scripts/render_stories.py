#!/usr/bin/env python3
"""html/ の *.html を 1080x1920 のPNGに書き出す（Chromeヘッドレス）"""
import glob
import os
import subprocess
import sys

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def main():
    if len(sys.argv) < 2:
        print("使い方: render_stories.py <htmlフォルダ> [pngフォルダ]")
        sys.exit(1)
    src = os.path.abspath(sys.argv[1])
    out = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else src
    os.makedirs(out, exist_ok=True)

    if not os.path.exists(CHROME):
        print(f"エラー: Google Chromeが見つかりません: {CHROME}")
        sys.exit(1)

    htmls = sorted(glob.glob(os.path.join(src, "*.html")))
    if not htmls:
        print(f"エラー: {src} に .html がありません")
        sys.exit(1)

    for html in htmls:
        name = os.path.splitext(os.path.basename(html))[0]
        png = os.path.join(out, f"{name}.png")
        result = subprocess.run(
            [
                CHROME,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                "--window-size=1080,1920",
                f"--screenshot={png}",
                f"file://{html}",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if os.path.exists(png):
            print(f"OK  {png}")
        else:
            print(f"失敗 {html}\n{result.stderr[-500:]}")
            sys.exit(1)

    print(f"\n完了: {len(htmls)}枚 → {out}")


if __name__ == "__main__":
    main()
