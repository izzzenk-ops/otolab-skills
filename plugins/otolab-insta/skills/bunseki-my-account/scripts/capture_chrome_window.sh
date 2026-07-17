#!/bin/bash
# Chromeの最前面ウィンドウをスクリーンショットする（プロフィールのスクショ用）。
# 使い方: bash capture_chrome_window.sh <出力.png>
#
# 仕組み: Chrome拡張のscreenshotはファイル保存できないため、macOSのscreencaptureを使う。
# Claude Desktopが直後にフォーカスを奪い返すことがあるので、
# 「Chrome前面化→撮影→明るさ判定（IGは白背景・Claudeは黒背景）→ダメならリトライ」を最大5回行う。
# 撮影後はブラウザUI（上部タブ/アドレスバー等）が写り込むので、PILで切り出すこと。
set -u
OUT="$1"
TMP="${OUT%.png}_try.png"

BOUNDS=$(osascript -l JavaScript -e '
const win = Application("Google Chrome").windows[0];
const b = win.bounds();
`${b.x},${b.y},${b.width},${b.height}`;
')
echo "chrome window bounds: $BOUNDS"

for i in 1 2 3 4 5; do
  osascript -e 'tell application "Google Chrome" to activate'
  sleep 0.4
  screencapture -x -R"$BOUNDS" "$TMP"
  BRIGHT=$(python3 - "$TMP" << 'EOF'
import sys
try:
    from PIL import Image
except ImportError:
    import subprocess, os
    # PILがない場合はtelop venvで再実行
    r = subprocess.run([os.path.expanduser("~/telop-tool/venv/bin/python3"), "-c",
        "import sys, statistics; from PIL import Image;"
        "img = Image.open(sys.argv[1]).convert('L').resize((50, 50));"
        "print(int(statistics.mean(img.getdata())))", sys.argv[1]],
        capture_output=True, text=True)
    print(r.stdout.strip()); sys.exit()
import statistics
img = Image.open(sys.argv[1]).convert('L').resize((50, 50))
print(int(statistics.mean(img.getdata())))
EOF
)
  echo "try $i: brightness=$BRIGHT"
  if [ "${BRIGHT:-0}" -gt 150 ]; then
    mv "$TMP" "$OUT"
    echo "SUCCESS -> $OUT"
    exit 0
  fi
  sleep 0.5
done
rm -f "$TMP"
echo "FAILED: Chromeウィンドウを前面で撮影できなかった（別Spaceのフルスクリーン等）。スクショなしで続行してよい" >&2
exit 1
