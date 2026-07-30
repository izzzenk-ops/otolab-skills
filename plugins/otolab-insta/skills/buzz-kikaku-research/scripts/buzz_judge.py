#!/usr/bin/env python3
"""バズ判定エンジン（けんじ式S級ランク・バズリサーチの定石ベース）。

リール一覧JSON（Chromeで収集）とフォロワー数から、
  - 各投稿のバズ判定（フォロワー×10以上 or 100万再生以上）
  - アカウントランク（S級 / 通常 / 影響力型 / バズなし）
  - 分析対象の選定（伸びてる群=バズ全部・上限つき／伸びてない群=下位の対照群）
  - 提出リールの合否（--submitted）
を計算して judge.json に保存し、人間が読めるサマリーを出力する。

使い方:
  python3 buzz_judge.py <reels.json> <output_dir> --followers 30000 \
      [--posts 25] [--submitted /reel/XXXX/] [--max-analyze 15] [--control 4]

reels.json の形式（bunseki-competitor-account と同じ）:
  {"<リールURL>": {"thumb": null, "views": "12.3万", "pinned": false}, ...}
  ※キーの挿入順 = グリッドの表示順（≒新しい順、ピン留めが先頭）

判定基準（出典: バズリサーチの定石＋けんじ式ランク）:
  - バズ認定: 再生数 >= フォロワー数×10、または >= 100万
  - S級ランク: バズ投稿5本以上 かつ バズ率20%以上（少ない投稿で量産＝再現性が高い）
  - 影響力型: 大きめのアカウント（フォロワー10万+）で全投稿が安定して高く
    （中央値 >= フォロワー×2）、アカウント内で突出した投稿がない（最高 <= 中央値×3）
    → 100万超えが並んでいても「本人の人気で回っている」ので企画・フックの参考にしない
    （教材の見極め:「すべての投稿が安定して伸びている → 個人の影響力」）
"""
import json
import re
import statistics
import sys
from pathlib import Path

MILLION = 1_000_000
SKYU_MIN_BUZZ = 5          # S級ランク: バズ本数の下限
SKYU_MIN_RATE = 0.20       # S級ランク: バズ率の下限
INFLUENCE_MIN_FOLLOWERS = 100_000  # 影響力型を疑い始めるフォロワー数
INFLUENCE_MEDIAN_X = 2   # 影響力型: 中央値がフォロワー×この倍数以上
OUTLIER_X = 3            # 「突出」= アカウント中央値のこの倍数以上


def parse_views(s):
    """「12.3万」「1,234」「1.2M」「45.6K」などを数値に変換。解釈不能ならNone。"""
    if not s:
        return None
    s = str(s).strip().replace(",", "").replace(" ", "")
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


def fmt(n):
    if n is None:
        return "?"
    if n >= 1e8:
        return f"{n/1e8:.1f}億"
    if n >= 1e4:
        return f"{n/1e4:.1f}万"
    return f"{n:,}"


def main():
    args = sys.argv[1:]
    followers = None
    posts = None
    submitted = None
    max_analyze, control_n = 15, 4
    if "--followers" in args:
        followers = parse_views(args[args.index("--followers") + 1])
    if "--posts" in args:
        posts = int(args[args.index("--posts") + 1])
    if "--submitted" in args:
        submitted = args[args.index("--submitted") + 1]
    if "--max-analyze" in args:
        max_analyze = int(args[args.index("--max-analyze") + 1])
    if "--control" in args:
        control_n = int(args[args.index("--control") + 1])
    if not followers:
        print("--followers <数> は必須です（例: --followers 3.2万）", file=sys.stderr)
        sys.exit(1)

    data = json.load(open(args[0]))
    outdir = Path(args[1])
    outdir.mkdir(parents=True, exist_ok=True)

    buzz_line = followers * 10
    items = []
    for i, (url, meta) in enumerate(data.items()):
        v = parse_views(meta.get("views"))
        is_buzz = v is not None and (v >= buzz_line or v >= MILLION)
        items.append({
            "url": url.split("?")[0],
            "id": reel_id(url),
            "grid_index": i,
            "pinned": bool(meta.get("pinned")),
            "views": v,
            "views_raw": meta.get("views"),
            "x_followers": round(v / followers, 1) if v else None,
            "is_buzz": is_buzz,
        })

    counted = [it for it in items if it["views"] is not None]
    views = [it["views"] for it in counted]
    buzz = sorted([it for it in counted if it["is_buzz"]],
                  key=lambda x: -x["views"])
    n = len(counted)
    median = int(statistics.median(views)) if views else None
    mean = int(statistics.mean(views)) if views else None
    vmax = max(views) if views else None
    buzz_rate = len(buzz) / n if n else 0.0

    # ---- アカウントランク ----------------------------------------------------
    # 影響力型: 大きめの垢で全体が高く、アカウント内の突出がない（=中身でなく人で回る）
    is_influence = (median is not None and vmax is not None
                    and followers >= INFLUENCE_MIN_FOLLOWERS
                    and median >= followers * INFLUENCE_MEDIAN_X
                    and vmax <= median * OUTLIER_X)
    if not counted:
        rank, rank_reason = "不明", "再生数が取得できなかった（非表示など）"
    elif is_influence:
        rank = "影響力型"
        rank_reason = (f"フォロワー{fmt(followers)}で中央値{fmt(median)}"
                       f"（フォロワーの{median/followers:.1f}倍）と全体的に高いのに、"
                       f"最高{fmt(vmax)}でも中央値の{vmax/median:.1f}倍＝突出した投稿がない。"
                       "どの投稿も安定して伸びている＝本人の人気で回っているアカウント。"
                       "企画・フックの参考にしない（アカウント全体の伸び方から見極め）")
    elif not buzz:
        rank = "バズなし"
        rank_reason = (f"バズ認定ライン({fmt(buzz_line)} or 100万)を超える投稿が0本。"
                       "このアカウントからは仮説を立てられない")
    elif len(buzz) >= SKYU_MIN_BUZZ and buzz_rate >= SKYU_MIN_RATE:
        rank = "S級"
        rank_reason = (f"バズ投稿{len(buzz)}本／収集{n}本（バズ率{buzz_rate*100:.0f}%）。"
                       "少ない投稿でバズを量産＝再現性高く伸ばせているアカウント。"
                       "バズ投稿を全本分析して伸びている理由を確実に言語化する")
    else:
        rank = "通常"
        rank_reason = f"バズ投稿{len(buzz)}本／収集{n}本（バズ率{buzz_rate*100:.0f}%）"

    # ---- 分析対象の選定 ------------------------------------------------------
    if rank == "影響力型":
        analyze, skipped_buzz, control = [], 0, []   # 参考にしないので分析しない
    else:
        analyze = buzz[:max_analyze]
        skipped_buzz = len(buzz) - len(analyze)
        non_buzz_sorted = sorted([it for it in counted if not it["is_buzz"]],
                                 key=lambda x: x["views"])
        control = non_buzz_sorted[:control_n]

    # ---- 提出リールの合否 ----------------------------------------------------
    verdict = None
    if submitted:
        sid = reel_id(submitted)
        hit = next((it for it in items if it["id"] == sid), None)
        if hit and hit["views"] is not None:
            v = hit["views"]
            if rank == "影響力型":
                verdict = {
                    "id": sid, "views": v, "x_followers": hit["x_followers"],
                    "passed": False,
                    "reason": (f"再生{fmt(v)}は数字としては大きいが、このアカウントは"
                               "影響力型（どの投稿も安定して高い）なので、この1本の"
                               "企画・フックが強い証拠にならない ❌ 別の投稿を探そう"),
                }
            else:
                passed = hit["is_buzz"]
                verdict = {
                    "id": sid, "views": v, "x_followers": hit["x_followers"],
                    "passed": passed,
                    "reason": (f"再生{fmt(v)}＝フォロワー{fmt(followers)}の"
                               f"{hit['x_followers']}倍"
                               + ("（100万超え）" if v >= MILLION else "")
                               + f" → 基準（10倍 or 100万）を"
                               + ("満たす ✅" if passed else "満たさない ❌")),
                }
        else:
            verdict = {"id": sid, "views": None, "passed": None,
                       "reason": "一覧に見つからない/再生数非表示（グリッド外の可能性。"
                                 "個別ページで再生数を確認する）"}

    result = {
        "followers": followers,
        "posts_total": posts,
        "buzz_line": buzz_line,
        "criteria": "views >= followers*10 OR views >= 1,000,000",
        "collected": len(items),
        "counted": n,
        "median": median, "mean": mean, "max": vmax,
        "buzz_count": len(buzz), "buzz_rate": round(buzz_rate, 3),
        "rank": rank, "rank_reason": rank_reason,
        "submitted_verdict": verdict,
        "analyze": analyze, "skipped_buzz": skipped_buzz,
        "control": control,
        "all": items,
    }
    out = outdir / "judge.json"
    json.dump(result, open(out, "w"), ensure_ascii=False, indent=1)

    # ---- サマリー ------------------------------------------------------------
    print(f"フォロワー: {fmt(followers)} / バズ認定ライン: {fmt(buzz_line)}"
          f"（フォロワー×10）or 100万")
    print(f"収集: {len(items)}本（再生数あり {n}本）"
          f" / 中央値 {fmt(median)} / 最高 {fmt(vmax)}")
    print(f"バズ投稿: {len(buzz)}本（バズ率 {buzz_rate*100:.0f}%）")
    print(f"ランク判定: {rank} — {rank_reason}")
    if verdict:
        print(f"提出リール: {verdict['reason']}")
    print(f"分析対象: 伸びてる群 {len(analyze)}本"
          + (f"（{skipped_buzz}本は上限で省略）" if skipped_buzz > 0 else "")
          + f" / 対照群 {len(control)}本")
    for it in analyze:
        print(f"  🔥 {fmt(it['views'])} ({it['x_followers']}x) {it['url']}")
    for it in control:
        print(f"  ・ {fmt(it['views'])} ({it['x_followers']}x) {it['url']}")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
