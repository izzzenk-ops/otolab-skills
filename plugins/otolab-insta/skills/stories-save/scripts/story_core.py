#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stories-save 共通処理。

  - 設定ファイル / 保存済み台帳 / ログ
  - ブラウザまたは cookies.txt からのログイン情報の取り出し
  - Instagram への問い合わせ（ストーリー一覧・ユーザーID解決）
  - 保存先のパス規則（<保存先>/<アカウント>/2026年/9月/26.9.4-1.jpg）
  - その日の1枚もの（コンタクトシート）の生成

このファイル単体では何もしない。add_account.py / save_stories.py / make_review.py から呼ばれる。
"""
from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

# Windows の cp932 コンソール/パイプで ✅ や ❌ を出すと落ちるので、出力をUTF-8に固定する
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

APP_ID = "936619743392459"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36")

CONFIG_NAME = "_設定.json"
STATE_NAME = "_保存済み.json"
LOG_NAME = "_ログ.txt"

DEFAULT_CONFIG = {
    "cookies_from": "chrome",   # chrome / firefox / edge / brave / safari / file
    "cookies_file": "",         # cookies_from が file のときだけ使う
    "accounts": [],             # [{"username": "...", "user_id": "...", "added": "2026-09-04"}]
    "keep_months": 0,           # 0なら消さない。12なら12か月より古い月フォルダを削除
}


class StoryError(Exception):
    """利用者に読ませる前提のエラー（原因と直し方を日本語で持つ）"""


# ---------------------------------------------------------------- 保存先

def base_dir() -> Path:
    """保存先のルート。Windows で Documents が OneDrive 配下のケースにも対応する。"""
    env = os.environ.get("STORIES_SAVE_DIR")
    if env:
        return Path(env).expanduser()
    home = Path.home()
    docs = home / "Documents"
    if not docs.exists():
        for alt in (home / "OneDrive" / "Documents", home / "OneDrive" / "ドキュメント", home / "ドキュメント"):
            if alt.exists():
                docs = alt
                break
    return docs / "Claude" / "Projects" / "ストーリー保存"


def account_dir(username: str) -> Path:
    return base_dir() / safe_name(username)


def day_paths(username: str, dt: datetime):
    """その日の「1枚もの」と「元データフォルダ」のパスを返す。"""
    stem = f"{dt.year % 100}.{dt.month}.{dt.day}"
    month_dir = account_dir(username) / f"{dt.year}年" / f"{dt.month}月"
    return month_dir / f"{stem}.jpg", month_dir / stem, stem


def safe_name(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", str(s)).strip() or "unknown"


# ---------------------------------------------------------------- 設定・状態・ログ

def load_config() -> dict:
    p = base_dir() / CONFIG_NAME
    cfg = dict(DEFAULT_CONFIG)
    if p.exists():
        try:
            cfg.update(json.loads(p.read_text(encoding="utf-8")))
        except Exception as e:
            raise StoryError(f"設定ファイルが読めません: {p}\n  ({e})\n  一度そのファイルを消せば作り直します。")
    return cfg


def save_config(cfg: dict) -> Path:
    p = base_dir() / CONFIG_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def load_state() -> dict:
    p = base_dir() / STATE_NAME
    if p.exists():
        try:
            st = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(st, dict):
                return st
        except Exception:
            pass
        # 壊れていた場合は捨てずに退避する（消すと同じストーリーを二重に保存してしまう）
        try:
            bak = p.with_suffix(".壊れていた.json")
            p.replace(bak)
            log(f"⚠ 保存済み台帳が壊れていたので {bak.name} に退避しました")
        except Exception:
            pass
    return {"last_success": "", "saved_ids": {}}


def save_state(st: dict):
    p = base_dir() / STATE_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def log(msg: str):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        p = base_dir() / LOG_NAME
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        # ログが育ちすぎたら古い方を捨てる
        if p.stat().st_size > 2_000_000:
            tail = p.read_text(encoding="utf-8").splitlines()[-2000:]
            p.write_text("\n".join(tail) + "\n", encoding="utf-8")
    except Exception:
        pass


def notify(title: str, message: str):
    """Mac は通知センターに出す。Windows/Linux はログのみ（呼び出し側が⚠ファイルも置く）。"""
    if platform.system() != "Darwin":
        return
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification {json.dumps(message)} with title {json.dumps(title)}'],
            capture_output=True, timeout=10)
    except Exception:
        pass


# ---------------------------------------------------------------- ログイン情報（Cookie）

class _QuietLogger:
    def debug(self, m): pass
    def info(self, m): pass
    def warning(self, m): pass
    def error(self, m): pass
    def to_screen(self, m): pass


WIN_CHROME_HINT = (
    "Windows版のChromeは、Chrome 127以降ログイン情報を外部から読み取れない仕組みに変わりました"
    "（Google側の仕様。こちらの工夫では突破できません）。次のどちらかにしてください。\n"
    "  A) Firefoxでインスタにログインして、設定の cookies_from を \"firefox\" にする\n"
    "  B) 拡張機能『Get cookies.txt LOCALLY』でCookieを1回書き出して、"
    "cookies_from を \"file\"、cookies_file にそのファイルのパスを書く"
)


def get_cookies(cfg: dict) -> dict:
    """ブラウザまたは cookies.txt から instagram.com のCookieを取り出す。"""
    src = (cfg.get("cookies_from") or "chrome").strip().lower()
    path = (cfg.get("cookies_file") or "").strip()

    if src == "file" or path:
        if not path:
            raise StoryError("cookies_from が file ですが cookies_file が空です。")
        f = Path(path).expanduser()
        if not f.exists():
            raise StoryError(f"Cookieファイルが見つかりません: {f}")
        from http.cookiejar import MozillaCookieJar
        jar = MozillaCookieJar()
        try:
            jar.load(str(f), ignore_discard=True, ignore_expires=True)
        except Exception as e:
            raise StoryError(f"Cookieファイルを読めません: {f}\n  ({e})\n"
                             "  『Get cookies.txt LOCALLY』でNetscape形式で書き出してください。")
        where = f"ファイル({f.name})"
    else:
        try:
            from yt_dlp.cookies import extract_cookies_from_browser
        except ImportError:
            raise StoryError("yt-dlp が入っていません。先に setup.py を実行してください。")
        try:
            jar = extract_cookies_from_browser(src, logger=_QuietLogger())
        except Exception as e:
            hint = "\n" + WIN_CHROME_HINT if os.name == "nt" and src in ("chrome", "edge", "brave") else ""
            raise StoryError(f"{src} からログイン情報を取り出せませんでした。\n  ({e}){hint}")
        where = f"{src}"

    cookies = {}
    for c in jar:
        if "instagram" in (c.domain or "") and c.value:
            cookies[c.name] = c.value

    if not cookies.get("sessionid") or not cookies.get("ds_user_id"):
        hint = "\n" + WIN_CHROME_HINT if os.name == "nt" and src in ("chrome", "edge", "brave") else ""
        raise StoryError(
            f"{where} にInstagramのログイン情報が見つかりませんでした。\n"
            f"  そのブラウザでインスタにログインしてから、もう一度実行してください。{hint}")
    return cookies


# ---------------------------------------------------------------- Instagram への問い合わせ

class IG:
    def __init__(self, cookies: dict):
        self.cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        self.me = cookies.get("ds_user_id", "")

    def _headers(self, api: bool):
        h = {"User-Agent": UA, "Referer": "https://www.instagram.com/",
             "Accept": "*/*", "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
             "Cookie": self.cookie_header}
        if api:
            h["X-IG-App-ID"] = APP_ID
        return h

    def _open(self, url: str, api=True, tries=3, timeout=40):
        last = None
        for i in range(tries):
            try:
                req = urllib.request.Request(url, headers=self._headers(api))
                return urllib.request.urlopen(req, timeout=timeout).read()
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (401, 403):
                    raise StoryError(
                        "Instagramに拒否されました（ログインが切れている可能性が高いです）。\n"
                        "  ブラウザでインスタを開き直してログインし、もう一度実行してください。")
                if e.code in (429, 500, 502, 503):
                    if i < tries - 1:
                        time.sleep(5 * (i + 1) ** 2)
                    continue
                raise
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = e
                if i < tries - 1:
                    time.sleep(3 * (i + 1))
        raise StoryError(f"Instagramへの接続に失敗しました: {url}\n  ({last})")

    def json(self, url: str, api=True):
        raw = self._open(url, api=api)
        try:
            return json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            raise StoryError(f"Instagramの返事を読めませんでした: {url}")

    def blob(self, url: str) -> bytes:
        """画像ファイルの取得（CDNなのでAPIヘッダは付けない）"""
        return self._open(url, api=False)


def resolve_user_id(ig: IG, username: str):
    """@ユーザー名 → 内部ID。1アカウントにつき最初の1回だけ呼ぶ（結果は設定に保存する）。"""
    u = username.strip().lstrip("@").strip("/").lower()
    if not u:
        raise StoryError("アカウント名が空です。")

    # 1) 検索エンドポイント（一番通りやすい）
    try:
        q = urllib.parse.quote(u)
        j = ig.json(f"https://www.instagram.com/api/v1/web/search/topsearch/?context=blended&query={q}&count=5")
        for entry in (j.get("users") or []):
            user = entry.get("user") or {}
            if (user.get("username") or "").lower() == u:
                return str(user["pk"]), user.get("username"), user.get("full_name") or ""
    except StoryError:
        raise
    except Exception:
        pass

    # 2) プロフィール情報エンドポイント（混み合っていると429になる）
    try:
        j = ig.json(f"https://www.instagram.com/api/v1/users/web_profile_info/?username={urllib.parse.quote(u)}")
        user = (j.get("data") or {}).get("user") or {}
        if user.get("id"):
            return str(user["id"]), user.get("username") or u, user.get("full_name") or ""
    except Exception:
        pass

    raise StoryError(
        f"@{u} が見つかりませんでした。\n"
        "  ・つづりを確認してください（プロフィールURLの instagram.com/ のうしろの文字）\n"
        "  ・非公開アカウントの場合、こちらがフォローして承認されている必要があります\n"
        "  ・立て続けに実行すると一時的に断られます。5〜10分あけて試してください")


def fetch_story_items(ig: IG, user_id: str):
    """そのアカウントの、今この瞬間表示できるストーリー（過去24時間分）を返す。"""
    j = ig.json(f"https://i.instagram.com/api/v1/feed/reels_media/?reel_ids={user_id}")
    reel = (j.get("reels") or {}).get(str(user_id)) or {}
    return reel.get("items") or [], (reel.get("user") or {})


# ---------------------------------------------------------------- 1枚分の情報の取り出し

def _pick_image(item: dict):
    cands = ((item.get("image_versions2") or {}).get("candidates") or [])
    cands = [c for c in cands if c.get("url")]
    if not cands:
        return None
    return sorted(cands, key=lambda c: -(c.get("width") or 0))[0]


def _collect_links(item: dict):
    """リンクスタンプのURLを拾う（スタンプの形式が数種類あるので広めに探す）"""
    found = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("url", "web_uri", "link_url") and isinstance(v, str) and v.startswith("http"):
                    if not re.search(r"(cdninstagram|fbcdn|instagram\.com/static)", v):
                        found.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for key in ("story_link_stickers", "story_bloks_stickers", "story_cta"):
        walk(item.get(key))
    seen, out = set(), []
    for u in found:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def item_meta(item: dict) -> dict:
    """保存する1枚分のメタ情報。あとで見返すときに効くものだけ拾う。"""
    taken = int(item.get("taken_at") or 0)
    is_video = bool(item.get("video_versions"))
    meta = {
        "id": str(item.get("pk") or item.get("id") or ""),
        "taken_at": taken,
        "time": datetime.fromtimestamp(taken).strftime("%H:%M") if taken else "",
        "kind": "video" if is_video else "image",
        "seconds": round(float(item.get("video_duration") or 0), 1) if is_video else 0,
    }
    links = _collect_links(item)
    if links:
        meta["links"] = links
    mentions = [m.get("user", {}).get("username") for m in (item.get("reel_mentions") or [])]
    mentions = [m for m in mentions if m]
    if mentions:
        meta["mentions"] = mentions
    tags = [h.get("hashtag", {}).get("name") for h in (item.get("story_hashtags") or [])]
    tags = [t for t in tags if t]
    if tags:
        meta["hashtags"] = tags
    polls = []
    for p in (item.get("story_polls") or []):
        st = p.get("poll_sticker") or {}
        q = st.get("question")
        opts = [t.get("text") for t in (st.get("tallies") or []) if t.get("text")]
        if q or opts:
            polls.append({"question": q, "options": opts})
    if polls:
        meta["polls"] = polls
    qs = [((q.get("question_sticker") or {}).get("question")) for q in (item.get("story_questions") or [])]
    qs = [q for q in qs if q]
    if qs:
        meta["questions"] = qs
    music = None
    for m in (item.get("story_music_stickers") or []):
        info = ((m.get("music_asset_info")) or {})
        if info.get("title"):
            music = f"{info.get('title')} / {info.get('display_artist') or ''}".strip(" /")
            break
    if music:
        meta["music"] = music
    feed = item.get("story_feed_media") or []
    if feed:
        code = (feed[0] or {}).get("media_code")
        if code:
            meta["repost"] = f"https://www.instagram.com/p/{code}/"
    return meta


# ---------------------------------------------------------------- 1枚もの（コンタクトシート）

_FONT_CANDIDATES = [
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W5.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "C:/Windows/Fonts/YuGothB.ttc",
    "C:/Windows/Fonts/YuGothM.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
]
_font_path_cache = None


def jp_font(size: int):
    from PIL import ImageFont
    global _font_path_cache
    if _font_path_cache is None:
        _font_path_cache = ""
        for p in _FONT_CANDIDATES:
            if Path(p).exists():
                _font_path_cache = p
                break
    if _font_path_cache:
        try:
            return ImageFont.truetype(_font_path_cache, size)
        except Exception:
            pass
    return ImageFont.load_default()


BG = (250, 249, 247)
INK = (38, 36, 34)
SUB = (140, 134, 128)
CORAL = (240, 120, 100)
LINE = (228, 223, 216)
CARD = (238, 234, 229)


def build_contact_sheet(entries, day_dir: Path, out_path: Path, username: str, dt: datetime):
    """その日の全ストーリーを1枚のJPEGに並べる。entries は info.json の items（時刻順）。"""
    from PIL import Image, ImageDraw

    COLS, TW, GAP, PAD, CAPH, HEADH = 5, 300, 22, 40, 44, 118
    TH = int(TW * 16 / 9)
    n = max(len(entries), 1)
    cols = min(COLS, n)
    rows = (n + COLS - 1) // COLS
    wd = "月火水木金土日"[dt.weekday()]
    n_img = sum(1 for e in entries if e.get("kind") != "video")
    n_vid = len(entries) - n_img
    head1 = f"@{username}"
    head2 = (f"{dt.year}年{dt.month}月{dt.day}日({wd})に保存　ストーリー {len(entries)}枚"
             f"（画像{n_img}・動画{n_vid}）")

    W = PAD * 2 + cols * TW + (cols - 1) * GAP
    H = HEADH + PAD + rows * (TH + CAPH + GAP) - GAP + PAD

    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    need = int(max(probe.textlength(head1, font=jp_font(38)),
                   probe.textlength(head2, font=jp_font(24)))) + PAD * 2
    W = max(W, need)   # ストーリーが1〜2枚の日でも見出しが切れないようにする

    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)
    d.text((PAD, 32), head1, font=jp_font(38), fill=INK)
    d.text((PAD, 82), head2, font=jp_font(24), fill=SUB)
    d.line([(PAD, HEADH - 4), (W - PAD, HEADH - 4)], fill=LINE, width=2)

    for i, e in enumerate(entries):
        r, c = divmod(i, COLS)
        x = PAD + c * (TW + GAP)
        y = HEADH + PAD + r * (TH + CAPH + GAP)
        card = Image.new("RGB", (TW, TH), CARD)
        f = day_dir / (e.get("file") or "")
        if f.exists():
            try:
                im = Image.open(f).convert("RGB")
                im.thumbnail((TW, TH), Image.LANCZOS)
                card.paste(im, ((TW - im.width) // 2, (TH - im.height) // 2))
            except Exception:
                pass
        mask = Image.new("L", (TW, TH), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, TW - 1, TH - 1], 18, fill=255)
        canvas.paste(card, (x, y), mask)

        d.rounded_rectangle([x + 10, y + 10, x + 58, y + 46], 14, fill=(0, 0, 0))
        num = str(i + 1)
        d.text((x + 34 - 6 * len(num), y + 16), num, font=jp_font(22), fill=(255, 255, 255))
        if e.get("kind") == "video":
            label = f"▶ {e.get('seconds', 0):g}秒"
            d.rounded_rectangle([x + TW - 106, y + 10, x + TW - 10, y + 46], 14, fill=CORAL)
            d.text((x + TW - 96, y + 16), label, font=jp_font(20), fill=(255, 255, 255))

        # 前の日の夜に出たストーリーは「9/3 21:27」と日付も出す（保存日と違うため）
        t = e.get("time", "")
        taken = e.get("taken_at")
        if taken:
            td = datetime.fromtimestamp(taken)
            if (td.year, td.month, td.day) != (dt.year, dt.month, dt.day):
                t = f"{td.month}/{td.day} {t}"
        cap = f"{i + 1}　{t}"
        cf = jp_font(22)
        d.text((x + 4, y + TH + 10), cap, font=cf, fill=SUB)
        marks = []
        if e.get("links"):
            marks.append("リンク")
        if e.get("polls") or e.get("questions"):
            marks.append("質問")
        if e.get("repost"):
            marks.append("再シェア")
        if marks:
            # 絵文字は日本語フォントに入っていないので文字で出す
            d.text((x + 8 + d.textlength(cap, font=cf), y + TH + 10),
                   "　" + "・".join(marks), font=cf, fill=CORAL)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=88, optimize=True)
    return out_path
