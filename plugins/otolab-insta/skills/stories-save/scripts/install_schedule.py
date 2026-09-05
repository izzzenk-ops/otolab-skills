#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""毎朝の自動保存をパソコンに登録する（Mac=launchd / Windows=タスクスケジューラ）。

  登録:   python install_schedule.py
  状態:   python install_schedule.py --status
  解除:   python install_schedule.py --uninstall

9:00 / 9:30 / 10:30 / 12:00 / 15:00 / 19:00 の6回登録する。
save_stories.py はその日すでに成功していれば即終了するので、実際に保存が走るのは1日1回だけ。
朝9時にパソコンが閉じていても、その日のどこかで開けば拾える。
"""
import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from story_core import base_dir  # noqa: E402

LABEL = "com.otolab.stories-save"
TASK_NAME = "ストーリー保存"
TIMES = [(9, 0), (9, 30), (10, 30), (12, 0), (15, 0), (19, 0)]
SCRIPT = Path(__file__).resolve().parent / "save_stories.py"
VENV = Path.home() / ".bunseki-tools" / "venv"


def venv_python(windowless=False):
    if os.name == "nt":
        if windowless:
            p = VENV / "Scripts" / "pythonw.exe"
            if p.exists():
                return p
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


# ---------------------------------------------------------------- Mac

def plist_path():
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def mac_install():
    logf = base_dir() / "_ログ_自動実行.txt"
    logf.parent.mkdir(parents=True, exist_ok=True)
    intervals = "".join(
        f"\n    <dict><key>Hour</key><integer>{h}</integer>"
        f"<key>Minute</key><integer>{m}</integer></dict>" for h, m in TIMES)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{venv_python()}</string>
    <string>{SCRIPT}</string>
  </array>
  <key>StartCalendarInterval</key>
  <array>{intervals}
  </array>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>{logf}</string>
  <key>StandardErrorPath</key><string>{logf}</string>
</dict>
</plist>
"""
    p = plist_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(xml, encoding="utf-8")
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"], capture_output=True)
    r = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(p)], capture_output=True, text=True)
    if r.returncode != 0:
        r = subprocess.run(["launchctl", "load", "-w", str(p)], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"❌ 登録できませんでした: {r.stderr.strip() or r.stdout.strip()}")
        return 1
    print(f"✅ 登録しました: {p}")
    print("   " + " / ".join(f"{h}:{m:02d}" for h, m in TIMES))
    return 0


def mac_status():
    uid = os.getuid()
    r = subprocess.run(["launchctl", "print", f"gui/{uid}/{LABEL}"], capture_output=True, text=True)
    if r.returncode != 0:
        print("未登録です。")
        return 1
    for line in r.stdout.splitlines():
        if any(k in line for k in ("state =", "last exit code", "runs =")):
            print("  " + line.strip())
    print(f"✅ 登録済み: {plist_path()}")
    return 0


def mac_uninstall():
    uid = os.getuid()
    was = subprocess.run(["launchctl", "print", f"gui/{uid}/{LABEL}"], capture_output=True).returncode == 0
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"], capture_output=True)
    p = plist_path()
    if p.exists():
        p.unlink()
    elif not was:
        print("もともと登録されていませんでした（解除するものはありません）。")
        return 0
    print("✅ 自動保存を解除しました。")
    return 0


# ---------------------------------------------------------------- Windows

def win_xml():
    triggers = "".join(f"""
    <CalendarTrigger>
      <StartBoundary>2026-01-01T{h:02d}:{m:02d}:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>""" for h, m in TIMES)
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Instagramのストーリーを毎朝保存する（stories-save）</Description>
  </RegistrationInfo>
  <Triggers>{triggers}
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{os.environ.get("USERNAME", "")}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <Enabled>true</Enabled>
    <ExecutionTimeLimit>PT30M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{venv_python(windowless=True)}</Command>
      <Arguments>"{SCRIPT}"</Arguments>
    </Exec>
  </Actions>
</Task>
"""


def win_install():
    import tempfile
    xmlp = Path(tempfile.gettempdir()) / "stories_save_task.xml"
    xmlp.write_text(win_xml(), encoding="utf-16")
    r = subprocess.run(["schtasks", "/create", "/tn", TASK_NAME, "/xml", str(xmlp), "/f"],
                       capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    if r.returncode != 0:
        print(f"❌ 登録できませんでした:\n{out}")
        return 1
    print(f"✅ 登録しました: タスク名「{TASK_NAME}」")
    print("   " + " / ".join(f"{h}:{m:02d}" for h, m in TIMES))
    print("   （パソコンが閉じていた回は、次に開いたときにまとめて1回だけ実行されます）")
    return 0


def win_status():
    r = subprocess.run(["schtasks", "/query", "/tn", TASK_NAME, "/v", "/fo", "list"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("未登録です。")
        return 1
    for line in r.stdout.splitlines():
        if any(k in line for k in ("次回", "Next Run", "前回", "Last Run", "状態", "Status", "結果", "Result")):
            print("  " + line.strip())
    return 0


def win_uninstall():
    r = subprocess.run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"], capture_output=True, text=True)
    if r.returncode != 0:
        print("もともと登録されていませんでした（解除するものはありません）。")
        return 0
    print("✅ 自動保存を解除しました。")
    return 0


# ----------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args()

    is_win = os.name == "nt"
    if not SCRIPT.exists():
        print(f"❌ 本体が見つかりません: {SCRIPT}")
        return 1
    if not venv_python().exists():
        print(f"❌ 先に setup.py を実行してください（{venv_python()} が無い）")
        return 1

    print(f"OS: {platform.system()}")
    if a.status:
        return win_status() if is_win else mac_status()
    if a.uninstall:
        return win_uninstall() if is_win else mac_uninstall()
    if is_win:
        return win_install()
    if platform.system() != "Darwin":
        print("❌ このOSの自動登録には対応していません（Mac / Windows のみ）。cron等で "
              f"{venv_python()} {SCRIPT} を1日数回動かしてください。")
        return 1
    return mac_install()


if __name__ == "__main__":
    sys.exit(main())
