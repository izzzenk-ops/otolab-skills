#!/usr/bin/env python3
"""stories-save 環境セットアップ（Mac / Windows / Linux 共通・pip完結）。

使い方:
  Mac/Linux :  python3 setup.py
  Windows   :  python setup.py

やること（冪等・何度流してもよい）:
  - ~/.bunseki-tools/venv（他の分析スキルと共通の仮想環境）を作る
  - pip で yt-dlp（Cookie読み取り用）と Pillow（画像合成用）を入れる
  - Homebrew も ffmpeg も不要

前提: Python 3.9+ が入っていること。
  - Mac は通常 python3 が使える（無ければ Xcode Command Line Tools で入る）
  - Windows は https://www.python.org からインストール（"Add to PATH"にチェック）
"""
import os
import platform
import subprocess
import sys
import venv
from pathlib import Path

VENV_DIR = Path.home() / ".bunseki-tools" / "venv"


def venv_python(vdir):
    if os.name == "nt":
        return vdir / "Scripts" / "python.exe"
    return vdir / "bin" / "python"


def pip_install(py, pkgs):
    return subprocess.run([str(py), "-m", "pip", "install", "--upgrade", *pkgs]).returncode == 0


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except Exception:
            pass
    print("stories-save セットアップ", flush=True)
    print(f"  OS: {platform.system()} / arch: {platform.machine()} / python: {sys.version.split()[0]}")

    py = venv_python(VENV_DIR)
    if not py.exists():
        print(f"  仮想環境を作成: {VENV_DIR}")
        VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)
    else:
        print(f"  仮想環境あり: {VENV_DIR}")

    ok = True
    ok &= pip_install(py, ["pip"])
    ok &= pip_install(py, ["yt-dlp", "pillow"])

    check = subprocess.run(
        [str(py), "-c", "import yt_dlp, PIL; print('yt_dlp=' + yt_dlp.version.__version__); print('pillow=' + PIL.__version__)"],
        capture_output=True, text=True)
    print(check.stdout.strip() or check.stderr.strip())

    if not ok or check.returncode != 0:
        print("❌ セットアップに失敗しました。上のエラーを見てください。")
        sys.exit(1)

    print(f"OS: {platform.system()}")
    print(f"✅ セットアップ完了。以下の python で実行してください: {py}")


if __name__ == "__main__":
    main()
