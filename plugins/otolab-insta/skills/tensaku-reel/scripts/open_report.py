#!/usr/bin/env python3
"""report.html を既定ブラウザ（可能ならChrome）で開く。Mac/Windows/Linux非依存。

  python open_report.py <report.html のパス>
"""
import os
import subprocess
import sys
import webbrowser
from pathlib import Path


def main():
    path = Path(sys.argv[1]).resolve()
    url = path.as_uri()
    sysname = sys.platform

    # まずChromeを試し、ダメなら既定ブラウザ
    try:
        if sysname == "darwin":
            subprocess.run(["open", "-a", "Google Chrome", str(path)], check=True)
            return
        if os.name == "nt":                 # Windows
            # start 経由でChrome（無ければ既定）
            if subprocess.run(["cmd", "/c", "start", "chrome", url]).returncode == 0:
                return
    except Exception:
        pass
    webbrowser.open(url)


if __name__ == "__main__":
    main()
