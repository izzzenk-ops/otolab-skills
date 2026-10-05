#!/usr/bin/env python3
"""ストーリーの背景写真を1枚作る（ChatGPTの契約に付いている Codex を使う。追加料金なし）

使い方:
  python3 gen_image.py --check
      → Codex が使えるかを調べて、日本語で結果を出す（ヒアリングのときに使う）
  python3 gen_image.py <出力.png> --kind tetemoto|kuukan --scene "英語で場面" [--style "英語で色や雰囲気"] [--ref 参考画像 ...]
      tetemoto … 手元のアップ（主役は下半分・上は空き）
      kuukan   … 人のいない空間・物の引き（部屋・食卓・窓辺など）

守ること（スキル側の方針）
  - 人の顔・本人に見える人物は作らない（本人の写真のように見えるAI画像は誤認のもとになるため）
  - アフィリエイト等の商品そのものは描かない（実物と違う写真になるため。商品は本人の写真か公式素材）
  - 写真に文字を描かせない（日本語が崩れる。文字は story.html で重ねる）
"""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

BASE = ("Vertical 9:16 smartphone photo for an Instagram story, shot on iPhone in portrait mode, realistic and slightly imperfect. "
        "Shallow depth of field: only the main subject is sharp. Leave calm empty space in the upper 40 percent for text. "
        "Soft natural light, low contrast, subtle film grain, quiet everyday mood. "
        "No people's faces, no person shown as a full figure, no product packaging, no text, no letters, no logos, no brand names.")
KIND = {
    "tetemoto": "Close-up of hands and objects; the subject sits in the lower half of the frame.",
    "kuukan": "A medium-wide shot of an empty space or objects without people; the subject sits in the lower half of the frame.",
}
DEFAULT_STYLE = "Muted warm greige and beige color grade, slightly underexposed."


def find_codex():
    cands = []
    sysname = platform.system()
    if sysname == "Darwin":
        cands += ["/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex",
                  "/Applications/ChatGPT.app/Contents/Resources/codex",
                  os.path.expanduser("~/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex")]
    elif sysname == "Windows":
        la = os.environ.get("LOCALAPPDATA", "")
        pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        for base in [os.path.join(la, "Programs", "ChatGPT"), os.path.join(pf, "ChatGPT")]:
            cands += [os.path.join(base, r"resources\codex-cli\bin\codex.exe"),
                      os.path.join(base, r"resources\codex.exe")]
    p = shutil.which("codex")
    if p:
        cands.append(p)
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


def check():
    c = find_codex()
    if not c:
        print("NG: ChatGPTの画像づくりの道具が見つかりませんでした。")
        print("  ・ChatGPTの有料プランを契約している人 → ChatGPTのデスクトップアプリを入れてログインしてから、もう一度試してください。")
        print("  ・契約していない／お金をかけたくない人 → 背景は自分の写真か一色で作れます（このまま進めてOK）。")
        sys.exit(2)
    print("OK: ChatGPTの画像づくりが使えます。")
    print("  ChatGPTのデスクトップアプリにログインした状態にしておいてください。画像は1枚1〜2分かかります。")
    print("  画像を作るにはChatGPTの有料プラン（Plusなど）が必要です。無料プランでは作れません。")


def main():
    if "--check" in sys.argv:
        check()
        return
    args = sys.argv[1:]
    if not args or args[0].startswith("--"):
        print(__doc__)
        sys.exit(1)
    out = Path(args[0]).resolve()
    kind, scene, style, refs = "tetemoto", "", DEFAULT_STYLE, []
    i = 1
    while i < len(args):
        if args[i] == "--kind" and i + 1 < len(args):
            kind = args[i + 1]; i += 2
            if kind not in KIND:
                print(f"エラー: --kind は {' / '.join(KIND)} のどれかです")
                sys.exit(1)
        elif args[i] == "--scene" and i + 1 < len(args):
            scene = args[i + 1]; i += 2
        elif args[i] == "--style" and i + 1 < len(args):
            style = args[i + 1]; i += 2
        elif args[i] == "--ref":
            i += 1
            while i < len(args) and not args[i].startswith("--"):
                refs.append(str(Path(args[i]).resolve())); i += 1
        else:
            i += 1
    if not scene:
        print("エラー: --scene（何を写すか・英語）が必要です")
        sys.exit(1)
    codex = find_codex()
    if not codex:
        check()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()  # 前の画像を成功と見まちがえないように
    prompt = f"{BASE} {KIND.get(kind, KIND['tetemoto'])} {style} Scene: {scene}"
    ref_note = "Use the attached image(s) only as a reference for color and mood. " if refs else ""
    instr = (f"Use your built-in image generation tool to create exactly one image. {ref_note}Prompt: {prompt}\n"
             f"Copy the final PNG to: {out}\nReply with the saved path only.")
    cmd = [codex, "exec", "--skip-git-repo-check", "--sandbox", "workspace-write", "-C", str(out.parent), instr]
    for r in refs:
        cmd += ["-i", r]
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600)
    except subprocess.TimeoutExpired:
        print("時間切れ: 10分たっても画像ができませんでした。少し時間をおいて、もう一度試してください。")
        sys.exit(1)
    if out.exists():
        print(out)
    else:
        print("画像を作れませんでした。考えられる原因：ChatGPTアプリのログイン切れ／使える量の上限（数時間〜数日で回復）／無料プラン（画像は有料プランのみ）。")
        print("この枚は、手持ちの写真か一色の背景で進められます。")
        tail = "\n".join((r.stderr or r.stdout or "").strip().splitlines()[-5:])
        if tail:
            print("（詳細）" + tail)
        sys.exit(1)


if __name__ == "__main__":
    main()
