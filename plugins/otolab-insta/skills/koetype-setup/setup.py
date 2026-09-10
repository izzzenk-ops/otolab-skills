#!/usr/bin/env python3
"""こえタイプの導入を機械的に進める道具。

このスクリプトは判断をしない。「今どうなっているか」を調べて日本語で報告し、
指示された1手だけを実行する。次に何をするかはスキル側（Claude）が決める。

  python3 setup.py status        いまどこまで進んでいるかを報告する
  python3 setup.py install       アプリを取ってきて /Applications に置き、起動する
  python3 setup.py setkey <KEY>  GeminiのAPIキーを設定して、本当に使えるか確かめる
  python3 setup.py restart       アプリを再起動する
  python3 setup.py lastresult    直前に喋った結果がどうなったかを報告する
"""

import json
import os
import platform
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# 配布物の置き場（GitHubのReleases）。curl/urllibで取るので隔離の印が付かず、
# 「開発元を検証できません」の警告は出ない。
DOWNLOAD_URL = "https://github.com/izzzenk-ops/koetype/releases/latest/download/koetype.zip"

APP = Path("/Applications/こえタイプ.app")
SUPPORT = Path.home() / "Library/Application Support/KoeType"
CONFIG = SUPPORT / "config.json"
LOG = SUPPORT / "koetype.log"
BIN = APP / "Contents/MacOS/koetype"


def say(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- 調べる

def app_running():
    r = subprocess.run(["pgrep", "-f", "MacOS/koetype"], capture_output=True)
    return r.returncode == 0


def read_startup_lines():
    """アプリが起動時に書く「権限」「マイクの許可」の行を新しい順に探す。"""
    if not LOG.exists():
        return {}
    lines = LOG.read_text(errors="replace").splitlines()
    found = {}
    for line in reversed(lines):
        if "権限 →" in line and "perm" not in found:
            found["perm"] = line
        if "マイクの許可:" in line and "mic" not in found:
            found["mic"] = line
        if len(found) == 2:
            break
    return found


def permission_state():
    """入力監視・アクセシビリティ・マイクの状態を返す。"""
    s = read_startup_lines()
    perm = s.get("perm", "")
    mic = s.get("mic", "")
    return {
        "入力監視": "OK" if "入力監視(キー検知)=OK" in perm else "未許可",
        "アクセシビリティ": "OK" if "アクセシビリティ(貼り付け)=OK" in perm else "未許可",
        "マイク": "OK" if "許可済み" in mic else "未許可",
    }


def load_cfg():
    if CONFIG.exists():
        try:
            return json.loads(CONFIG.read_text())
        except Exception:
            return {}
    return {}


def cmd_status():
    say("=== こえタイプ 導入状況 ===")
    mac = platform.mac_ver()[0]
    arch = platform.machine()
    say(f"macOS: {mac} / CPU: {arch}")
    if arch != "arm64":
        say("⚠ このアプリは Apple Silicon 専用です。Intel Macでは動きません。")
    major = int(mac.split(".")[0]) if mac else 0
    if major and major < 13:
        say("⚠ macOS 13 以降が必要です。")

    say(f"アプリ: {'あり' if APP.exists() else 'なし'}"
        f"{' / 起動中' if app_running() else ' / 停止中' if APP.exists() else ''}")

    if APP.exists():
        for name, state in permission_state().items():
            say(f"許可 {name}: {state}")

    cfg = load_cfg()
    key = cfg.get("gemini_api_key") or ""
    say(f"APIキー: {'設定済み' if key else '未設定'}")
    say(f"マイク: {cfg.get('audio_device', '(未設定)')}")

    done = (APP.exists() and key
            and all(v == "OK" for v in permission_state().values()))
    say(f"総合: {'すぐ使えます' if done else 'まだ設定が残っています'}")


# ---------------------------------------------------------------- 入れる

def cmd_install(url=None):
    url = url or DOWNLOAD_URL
    zip_path = Path("/tmp/koetype_dl.zip")
    say(f"ダウンロード中… {url}")
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(url, context=ctx, timeout=120) as r, \
                open(zip_path, "wb") as f:
            shutil.copyfileobj(r, f)
    except Exception as e:
        say(f"NG ダウンロードできませんでした: {e}")
        return 1
    say(f"取得しました（{zip_path.stat().st_size // 1024 // 1024}MB）")

    # ブラウザ以外で取ったファイルには隔離の印が付かない。念のため確認して外す
    q = subprocess.run(["xattr", "-p", "com.apple.quarantine", str(zip_path)],
                       capture_output=True)
    if q.returncode == 0:
        subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(zip_path)])
        say("隔離の印を外しました")

    if app_running():
        subprocess.run(["pkill", "-f", "MacOS/koetype"])
        time.sleep(1)
    if APP.exists():
        shutil.rmtree(APP)
    say("展開中…")
    # Pythonのzipfileは日本語のフォルダ名を壊し、実行権限も落とす。
    # macOS標準の ditto を使う（名前も権限も署名もそのまま展開できる）
    d = subprocess.run(["/usr/bin/ditto", "-x", "-k", str(zip_path), "/Applications"],
                       capture_output=True, text=True)
    if d.returncode != 0 or not APP.exists():
        say(f"NG 展開に失敗しました: {d.stderr[:200]}")
        return 1
    subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(APP)],
                   capture_output=True)

    v = subprocess.run(["codesign", "--verify", "--strict", str(APP)],
                       capture_output=True, text=True)
    say(f"署名の確認: {'OK' if v.returncode == 0 else 'NG ' + v.stderr[:120]}")

    subprocess.run(["open", str(APP)])
    time.sleep(6)
    say(f"起動: {'OK' if app_running() else 'NG 立ち上がりませんでした'}")
    say("インストール完了。次は権限3つの許可です。")
    return 0


def cmd_restart():
    subprocess.run(["pkill", "-f", "MacOS/koetype"], capture_output=True)
    time.sleep(2)
    subprocess.run(["open", str(APP)])
    time.sleep(6)
    say(f"再起動: {'OK' if app_running() else 'NG'}")
    for name, state in permission_state().items():
        say(f"許可 {name}: {state}")


# ---------------------------------------------------------------- APIキー

def cmd_setkey(key):
    key = key.strip()
    if not key:
        say("NG キーが空です")
        return 1

    say("キーが本当に使えるか確かめます…")
    ok, message = check_key(key)
    say(message)
    if not ok:
        say("キーは保存していません。上の案内にしたがって取り直してください。")
        return 1

    SUPPORT.mkdir(parents=True, exist_ok=True)
    cfg = load_cfg()
    cfg["gemini_api_key"] = key
    cfg["provider"] = "gemini"
    tmp = CONFIG.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    os.chmod(tmp, 0o600)
    os.replace(tmp, CONFIG)
    say("キーを保存しました（このMacの中だけに保存され、他へは送られません）")
    cmd_restart()
    return 0


def check_key(key):
    """キーを1回だけ試して、結果を受講生に分かる言葉で返す。"""
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-3.1-flash-lite:generateContent?key=" + key)
    body = json.dumps({"contents": [{"parts": [{"text": "1と答えて"}]}]}).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            if r.status == 200:
                return True, "OK キーは正常に使えます"
            return False, f"NG 予期しない応答: {r.status}"
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")
        return False, diagnose(e.code, text)
    except Exception as e:
        return False, f"NG つながりませんでした（ネット接続を確認してください）: {e}"


def diagnose(code, text):
    """今日までに実際に遭遇したエラーを、原因と次の一手に翻訳する。"""
    if code == 400 and "API key not valid" in text:
        return ("NG キーが正しくありません。\n"
                "   → コピーし損ねている可能性があります。もう一度コピーし直してください。")
    if code == 403:
        return ("NG このキーではGemini APIが有効になっていません。\n"
                "   → https://aistudio.google.com/apikey で作り直してください。\n"
                "     Google Cloudの管理画面で作ったキーは、制限がかかっていて使えないことがあります。")
    if code == 429 and "prepayment" in text:
        return ("NG 支払い情報が紐づいたプロジェクトで作られたキーです。無料枠が使えません。\n"
                "   → https://aistudio.google.com/apikey で「API キーを作成」→\n"
                "     プロジェクト欄で必ず「＋ プロジェクトを作成」を選んで、\n"
                "     新しいプロジェクトでキーを作り直してください。")
    if code == 429:
        return ("NG 今日の無料枠を使い切っています。\n"
                "   → 明日また使えます。キー自体は正しいので、そのままお待ちください。")
    if code == 503:
        return ("NG Gemini側が混み合っています（キーの問題ではありません）。\n"
                "   → 少し待ってからもう一度お試しください。")
    return f"NG エラー {code}: {text[:200]}"


# ---------------------------------------------------------------- 結果確認

def cmd_lastresult():
    if not LOG.exists():
        say("まだ使われていません")
        return
    lines = LOG.read_text(errors="replace").splitlines()
    keys = ("完了", "声が入っていない", "無音のため", "聞き取れ", "失敗", "エラー",
            "キー検知", "録音開始", "マイクが開きました")
    hits = [l for l in lines if any(k in l for k in keys)][-12:]
    if not hits:
        say("まだ喋った記録がありません")
        return
    say("=== 直近の記録 ===")
    for l in hits:
        say(" ", l)
    last = [l for l in hits if "完了" in l]
    if last:
        say(f"\n判定: 成功しています（{last[-1].split('完了')[1].strip()}）")
    else:
        say("\n判定: まだ成功した記録がありません")


# ---------------------------------------------------------------- 入口

if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "status"
    if cmd == "status":
        cmd_status()
    elif cmd == "install":
        sys.exit(cmd_install(args[1] if len(args) > 1 else None))
    elif cmd == "setkey":
        if len(args) < 2:
            say("使い方: setup.py setkey <APIキー>")
            sys.exit(1)
        sys.exit(cmd_setkey(args[1]))
    elif cmd == "restart":
        cmd_restart()
    elif cmd == "lastresult":
        cmd_lastresult()
    else:
        say(__doc__)
