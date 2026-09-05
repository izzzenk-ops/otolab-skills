#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""保存したいアカウントを登録・削除・一覧する。

  登録:  python add_account.py <ユーザー名 または プロフィールURL> [...]
  一覧:  python add_account.py --list
  削除:  python add_account.py --remove <ユーザー名>
  ログイン元の変更: python add_account.py --cookies-from firefox
                    python add_account.py --cookies-file "C:/Users/xxx/cookies.txt"

ユーザーIDの問い合わせは登録のときだけ。以降の毎朝の保存では一切呼ばない。
"""
import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from story_core import (IG, StoryError, base_dir, get_cookies, load_config,  # noqa: E402
                        resolve_user_id, save_config)


SKIP_PATHS = {"stories", "p", "reel", "reels", "explore", "s", "tv", "highlights"}


def to_username(s: str) -> str:
    """@名前 / URL / ストーリーURL / 全角＠ のどれで渡されても、ユーザー名だけを取り出す。"""
    s = s.strip().strip("<>\"'")
    m = re.search(r"instagram\.com/([^/?#\s]+)(?:/([^/?#\s]+))?", s)
    if m:
        first, second = m.group(1), m.group(2)
        # https://www.instagram.com/stories/<ユーザー名>/<ID> のような形に対応する
        s = second if (first.lower() in SKIP_PATHS and second) else first
    return s.lstrip("@＠").strip("/").split("?")[0]


KNOWN_BROWSERS = ("brave", "chrome", "chromium", "edge", "firefox", "opera", "safari", "vivaldi", "whale", "file")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("accounts", nargs="*")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--remove")
    ap.add_argument("--cookies-from")
    ap.add_argument("--cookies-file")
    a = ap.parse_args()

    cfg = load_config()

    if a.cookies_from:
        name = a.cookies_from.strip().lower()
        if name not in KNOWN_BROWSERS:
            raise StoryError(f"『{a.cookies_from}』というブラウザは指定できません。\n"
                             f"  使えるのは: {' / '.join(KNOWN_BROWSERS)}")
        cfg["cookies_from"] = name
        if name != "file":
            cfg["cookies_file"] = ""
    if a.cookies_file:
        f = Path(a.cookies_file).expanduser()
        if not f.exists():
            raise StoryError(f"そのCookieファイルが見つかりません: {f}\n"
                             "  『Get cookies.txt LOCALLY』で書き出したファイルの場所を確認してください。")
        cfg["cookies_from"] = "file"
        cfg["cookies_file"] = str(f)
    if a.cookies_from or a.cookies_file:
        save_config(cfg)
        print(f"ログイン元を変更しました: {cfg['cookies_from']} {cfg.get('cookies_file') or ''}")

    if a.remove:
        u = to_username(a.remove).lower()
        before = len(cfg["accounts"])
        cfg["accounts"] = [x for x in cfg["accounts"] if x["username"].lower() != u]
        save_config(cfg)
        print(f"削除しました: @{u}" if len(cfg["accounts"]) < before else f"登録されていません: @{u}")

    if a.accounts:
        cookies = get_cookies(cfg)
        ig = IG(cookies)
        known = {x["username"].lower() for x in cfg["accounts"]}
        for raw in a.accounts:
            u = to_username(raw)
            if u.lower() in known:
                print(f"すでに登録済み: @{u}")
                continue
            uid, real, full = resolve_user_id(ig, u)
            cfg["accounts"].append({"username": real, "user_id": uid,
                                    "full_name": full, "added": date.today().isoformat()})
            known.add(real.lower())
            print(f"✅ 登録しました: @{real}（{full or '名前なし'}）")
        save_config(cfg)

    print()
    print(f"保存先: {base_dir()}")
    print(f"ログイン元: {cfg['cookies_from']} {cfg.get('cookies_file') or ''}")
    print("登録中のアカウント:")
    if not cfg["accounts"]:
        print("  （まだありません）")
    for x in cfg["accounts"]:
        print(f"  - @{x['username']}  {x.get('full_name') or ''}")


if __name__ == "__main__":
    try:
        main()
    except StoryError as e:
        print(f"\n❌ {e}")
        sys.exit(1)
