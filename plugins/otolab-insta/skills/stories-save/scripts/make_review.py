#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ためた1枚ものを、1週間分・1か月分でまとめて見返すHTMLを作る。

  直近1週間:  python make_review.py --days 7
  9月ぜんぶ:  python make_review.py --month 2026-09
  1アカウント: python make_review.py --days 7 --account xxx

作ったHTMLはそのままブラウザで開く（--no-open で開かない）。
"""
import argparse
import html
import json
import sys
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from story_core import StoryError, base_dir, day_paths, load_config  # noqa: E402

CSS = """
:root{--bg:#faf9f7;--ink:#262422;--sub:#8c8680;--line:#e4dfd8;--coral:#f07864;--card:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic",sans-serif;line-height:1.7}
.wrap{max-width:1100px;margin:0 auto;padding:32px 20px 80px}
h1{font-size:26px;margin:0 0 4px}
.lead{color:var(--sub);font-size:14px;margin:0 0 28px}
.day{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;margin:0 0 22px}
.day h2{font-size:18px;margin:0 0 2px}
.day .meta{color:var(--sub);font-size:13px;margin:0 0 12px}
.day img{width:100%;height:auto;border-radius:10px;display:block}
.notes{margin:14px 0 0;padding:12px 14px;background:#fbf7f5;border-radius:10px;font-size:13px}
.notes div{margin:2px 0}
.tag{display:inline-block;background:var(--coral);color:#fff;border-radius:999px;
  padding:1px 9px;font-size:11px;margin-right:6px}
a{color:#c2543f;word-break:break-all}
.empty{color:var(--sub);text-align:center;padding:60px 0}
"""


def collect(username, days):
    out = []
    for d in days:
        sheet, day_dir, stem = day_paths(username, datetime(d.year, d.month, d.day))
        if not sheet.exists():
            continue
        info = {}
        p = day_dir / "info.json"
        if p.exists():
            try:
                info = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                info = {}
        out.append((d, sheet, info))
    return out


def notes_html(info):
    rows = []
    def esc(x):
        return html.escape(str(x or ""))

    for i, e in enumerate(info.get("items", []), 1):
        bits = []
        for u in e.get("links", []):
            bits.append(f'<a href="{esc(u)}" target="_blank" rel="noopener">{esc(u)}</a>')
        for p in e.get("polls", []):
            bits.append("アンケート: " + esc(p.get("question")) + "（"
                        + " / ".join(esc(o) for o in (p.get("options") or [])) + "）")
        for q in e.get("questions", []):
            bits.append("質問箱: " + esc(q))
        if e.get("repost"):
            bits.append(f'投稿の再シェア: <a href="{esc(e["repost"])}" target="_blank" rel="noopener">{esc(e["repost"])}</a>')
        if e.get("mentions"):
            bits.append("メンション: " + ", ".join("@" + esc(m) for m in e["mentions"]))
        if e.get("hashtags"):
            bits.append("ハッシュタグ: " + ", ".join("#" + esc(t) for t in e["hashtags"]))
        if bits:
            rows.append(f'<div><span class="tag">{i}</span>' + " ／ ".join(bits) + "</div>")
    if not rows:
        return ""
    return '<div class="notes">' + "".join(rows) + "</div>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int)
    ap.add_argument("--month")           # 2026-09
    ap.add_argument("--account")
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()

    cfg = load_config()
    accounts = [x["username"] for x in cfg.get("accounts", [])]
    if a.account:
        want = a.account.lstrip("@＠").lower()
        hit = [x for x in accounts if x.lower() == want]
        if not hit:
            raise StoryError(f"@{want} は登録されていません。"
                             f"（登録中: {', '.join('@' + x for x in accounts) or 'なし'}）")
        accounts = hit
    if not accounts:
        print("登録されているアカウントがありません。")
        return 1

    today = date.today()
    if a.month:
        try:
            y, m = (int(x) for x in a.month.split("-"))
            date(y, m, 1)
        except Exception:
            raise StoryError(f"月の書き方が違います: {a.month}\n  「2026-09」のように書いてください。")
        first = date(y, m, 1)
        last = date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)
        days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
        title = f"{y}年{m}月のストーリー"
        stem = f"{y}-{m:02d}_1か月"
    else:
        n = a.days or 7
        days = [today - timedelta(days=i) for i in range(n - 1, -1, -1)]
        title = f"直近{n}日間のストーリー"
        stem = f"{today:%Y-%m-%d}_{n}日間"

    days = list(reversed(days))   # 新しい日を上に
    parts = []
    total = 0
    for username in accounts:
        found = collect(username, days)
        if not found:
            continue
        parts.append(f'<h1>@{username}</h1><p class="lead">{title}　{len(found)}日分</p>')
        for d, sheet, info in found:
            wd = "月火水木金土日"[d.weekday()]
            n_items = info.get("count", len(info.get("items", [])))
            total += n_items
            parts.append(
                f'<section class="day"><h2>{d.year}年{d.month}月{d.day}日({wd})</h2>'
                f'<p class="meta">{n_items}枚　{sheet.name}</p>'
                f'<img src="{sheet.as_uri()}" alt="{sheet.name}">'
                f'{notes_html(info)}</section>')

    body = "".join(parts) or '<p class="empty">この期間に保存されたストーリーはありません。</p>'
    html = (f'<!doctype html><html lang="ja"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{title}</title><style>{CSS}</style></head>'
            f'<body><div class="wrap">{body}</div></body></html>')

    out = base_dir() / "_振り返り" / f"{stem}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"✅ 作りました: {out}（{total}枚分）")
    if not a.no_open:
        webbrowser.open(out.as_uri())
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except StoryError as e:
        print(f"\n❌ {e}")
        sys.exit(1)
