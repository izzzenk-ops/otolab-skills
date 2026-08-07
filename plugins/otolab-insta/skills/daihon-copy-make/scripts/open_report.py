#!/usr/bin/env python3
"""report.html を既定ブラウザで開く（標準ライブラリのみ・venv不要・Mac/Win両対応）。"""
import os
import sys
import webbrowser


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: open_report.py <report.html>", file=sys.stderr)
        return 2
    path = os.path.abspath(os.path.expanduser(sys.argv[1]))
    if not os.path.exists(path):
        print(f"⚠ 見つかりません: {path}", file=sys.stderr)
        return 1
    webbrowser.open("file://" + path)
    print(f"✅ 開きました: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
