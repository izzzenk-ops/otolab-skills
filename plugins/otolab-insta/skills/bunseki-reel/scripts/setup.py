#!/usr/bin/env python3
"""bunseki-reel 環境セットアップ（Mac / Windows / Linux 共通・pip完結）。

使い方:
  Mac/Linux :  python3 setup.py
  Windows   :  python setup.py

やること（冪等・毎回流してよい）:
  - ~/.bunseki-tools/venv に専用の仮想環境を作る
  - pip で共通ツールを入れる: yt-dlp / imageio-ffmpeg（ffmpeg同梱）/ numpy
  - 文字起こしエンジンをOSで出し分け:
      Apple Silicon Mac → mlx-whisper（Metal・高速）
      それ以外(Windows等) → faster-whisper（CPU/GPU）
  - Homebrew も システムのffmpeg も不要（ffmpegは imageio-ffmpeg 同梱を使う）

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
    if os.name == "nt":                     # Windows
        return vdir / "Scripts" / "python.exe"
    return vdir / "bin" / "python"


def pip_install(py, pkgs):
    return subprocess.run([str(py), "-m", "pip", "install", "--upgrade", *pkgs]).returncode == 0


def main():
    print("bunseki-reel セットアップ")
    print(f"  OS: {platform.system()} / arch: {platform.machine()} / python: {sys.version.split()[0]}")

    is_apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"
    engine = "mlx-whisper" if is_apple_silicon else "faster-whisper"
    print(f"  文字起こしエンジン: {engine}")

    # venv 作成（無ければ）
    py = venv_python(VENV_DIR)
    if not py.exists():
        print(f"  仮想環境を作成: {VENV_DIR}")
        VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)
    else:
        print(f"  仮想環境あり: {VENV_DIR}")

    ok = True
    ok &= pip_install(py, ["pip"])
    ok &= pip_install(py, ["yt-dlp", "imageio-ffmpeg", "numpy"])
    ok &= pip_install(py, [engine])

    # 動作確認
    check = subprocess.run(
        [str(py), "-c",
         "import yt_dlp, imageio_ffmpeg, numpy; "
         "import importlib; "
         "b='mlx' if importlib.util.find_spec('mlx_whisper') else "
         "('faster' if importlib.util.find_spec('faster_whisper') else 'none'); "
         "print('backend='+b); print('ffmpeg='+imageio_ffmpeg.get_ffmpeg_exe())"],
        capture_output=True, text=True)
    print(check.stdout.strip() or check.stderr.strip())

    if ok and "backend=none" not in check.stdout:
        print("\n✅ セットアップ完了。以下の python でスクリプトを実行してください:")
        print(f"   {py}")
    else:
        print("\n⚠ 一部が未完了です。上のエラーを確認してください。")
        sys.exit(1)


if __name__ == "__main__":
    main()
