#!/usr/bin/env python3
"""リール一覧JSONから「伸びている上位N本＋最新M本」を選定し、統計を計算する。

使い方:
  python3 select_reels.py <reels.json> <output_dir> [--top 10] [--latest 5]

入力 reels.json の形式（Chromeのjavascript_toolで収集したもの）:
  {"<リールURL>": {"thumb": null, "views": "12.3万", "pinned": false}, ...}
  ※キーの挿入順 = グリッドの表示順（≒新しい順、ピン留めが先頭）

出力（output_dir に保存）:
  selection.json — 選定結果 [{url, id, thumb, views_raw, views, picks: ["top"|"latest"], grid_index}]
  stats.json     — 全体統計（本数・平均・中央値・最高・バズ率など）
"""
import json
import re
import statistics
import sys
from pathlib import Path


def parse_views(s):
    """「12.3万」「1,234」「1.2M」「45.6K」などを数値に変換。解釈不能ならNone。"""
    if not s:
        return None
    s = s.strip().replace(",", "").replace(" ", "")
    m = re.search(r"([\d.]+)(億|万|千|[KkMmB]?)", s)
    if not m:
        return None
    try:
        num = float(m.group(1))
    except ValueError:
        return None
    mult = {"億": 1e8, "万": 1e4, "千": 1e3, "K": 1e3, "k": 1e3,
            "M": 1e6, "m": 1e6, "B": 1e9, "": 1}[m.group(2)]
    return int(num * mult)


def reel_id(url):
    m = re.search(r"/(?:reel|p)/([^/?]+)", url)
    return m.group(1) if m else re.sub(r"\W+", "_", url)[-20:]


def main():
    args = sys.argv[1:]
    top_n, latest_n = 10, 5
    if "--top" in args:
        top_n = int(args[args.index("--top") + 1])
    if "--latest" in args:
        latest_n = int(args[args.index("--latest") + 1])

    data = json.load(open(args[0]))
    outdir = Path(args[1])
    outdir.mkdir(parents=True, exist_ok=True)

    items = []
    for i, (url, meta) in enumerate(data.items()):
        items.append({
            "url": url.split("?")[0],
            "id": reel_id(url),
            "thumb": meta.get("thumb"),
            "views_raw": meta.get("views", ""),
            "views": parse_views(meta.get("views", "")),
            "pinned": bool(meta.get("pinned")),
            "grid_index": i,
        })

    viewed = [it for it in items if it["views"] is not None]
    views_list = [it["views"] for it in viewed]

    # 最新M本：ピン留めを除いたグリッド先頭から
    latest = [it for it in items if not it["pinned"]][:latest_n]
    # 上位N本：再生数順
    top = sorted(viewed, key=lambda x: -x["views"])[:top_n]

    selection = {}
    for it in top:
        selection.setdefault(it["url"], {**it, "picks": []})["picks"].append("top")
    for it in latest:
        selection.setdefault(it["url"], {**it, "picks": []})["picks"].append("latest")
    sel_list = sorted(selection.values(), key=lambda x: x["grid_index"])

    stats = {
        "total_reels_collected": len(items),
        "reels_with_views": len(viewed),
        "views_mean": int(statistics.mean(views_list)) if views_list else None,
        "views_median": int(statistics.median(views_list)) if views_list else None,
        "views_max": max(views_list) if views_list else None,
        "views_min": min(views_list) if views_list else None,
        # バズ率 = 中央値の3倍を超えた本数の割合
        "buzz_count_3x_median": (
            sum(1 for v in views_list if v > 3 * statistics.median(views_list))
            if views_list else None
        ),
        "selected_count": len(sel_list),
        "overlap_top_and_latest": sum(1 for s in sel_list if len(s["picks"]) > 1),
    }

    json.dump(sel_list, open(outdir / "selection.json", "w"),
              ensure_ascii=False, indent=1)
    json.dump(stats, open(outdir / "stats.json", "w"),
              ensure_ascii=False, indent=1)

    print(f"collected: {stats['total_reels_collected']} reels "
          f"(views readable: {stats['reels_with_views']})")
    print(f"selected: {len(sel_list)} reels "
          f"(top {top_n} + latest {latest_n}, overlap {stats['overlap_top_and_latest']})")
    if stats["views_median"]:
        print(f"views median: {stats['views_median']:,} / mean: {stats['views_mean']:,} "
              f"/ max: {stats['views_max']:,}")
    for s in sel_list:
        mark = "+".join(s["picks"])
        print(f"  [{mark:10s}] {s['views_raw'] or '?':>8s}  {s['url']}")


if __name__ == "__main__":
    main()
