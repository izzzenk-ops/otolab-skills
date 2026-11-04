#!/usr/bin/env python3
"""otolab-skills 同期ヘルパー

~/.claude/skills/ の最新スキルを、このマーケットプレイス（受講生向け配布物）に
反映するためのツール。原本を直したあと、これを1回走らせるだけでよくなる。

やること:
  1. 対象スキルを ~/.claude/skills/<name> から plugins/otolab-insta/skills/<name> へ
     まるごと上書きコピー（__pycache__ / *.pyc は除外）
  2. SKILL.md の「## 出す前の書き癖チェック」節（次の「## 」まで）を、
     templates/kakikuse_jukousei.md の受講生向けの中身に置き換える（原本は触らない）
  3. 受講生向けの一般化ルール（REPLACEMENTS）を全テキストに適用
  4. 危険語チェック（REVIEW_TERMS）: 人の判断が要る個人名・ブランド名・招待コード等が
     残っていないか走査。1つでも残っていたら **commitせず停止** して場所を表示する
  5. 問題なければ git add。 --commit でコミット、--push でコミット＋push

使い方:
  python3 sync.py            # コピー＋一般化＋チェック＋stageまで（差分を目視できる）
  python3 sync.py --commit   # 上に加えてローカルコミット
  python3 sync.py --push     # 上に加えて git push（＝受講生への公開反映）

ルールを足したいとき: 下の REPLACEMENTS / REVIEW_TERMS を編集する。
"""
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
SKILLS_SRC = Path.home() / ".claude" / "skills"
DEST = REPO / "plugins" / "otolab-insta" / "skills"

# 配布するスキル（原本フォルダ名）
SKILLS = [
    "bunseki-reel", "bunseki-competitor-account", "bunseki-my-account",
    "insta-concept-design", "daihon-copy-make", "daihon-kyaba-vlog",
    "concept-brush-up", "daihon-tensaku", "cut-silence", "genre-sentei",
    "buzz-kikaku-research", "concept-research", "tensaku-reel",
    "stories-bunseki", "stories-days", "stories-launch", "stories-affiliate",
    "stories-save", "skill-sekkei", "koetype-setup", "reel-henshu-afreco",
]

# 受講生向けの一般化（before → after）。順序どおり適用。上ほど先。
# ※短い語（desse等）より、それを含む長い語（desse-reel-script等）を必ず先に置く。
REPLACEMENTS = [
    # 受講生に配布していないスキルへの参照を落とす（ストーリーズ4スキル由来）。
    # ※短い変種より先に、長い一文まるごとを先に消す
    ("おとばな（THE OTOGIBANASHI SUPPLY）のBOX販売ストーリーズは happybox-story-plan を使う。", ""),
    ("おとばな（THE OTOGIBANASHI SUPPLY）のBOX販売は happybox-story-plan を使う。", ""),
    ("ThreadsのAmazonアフィリは threads-affiliate を使う。", ""),
    # 招待コード（値は載せない。講座内で配布）
    ("otolabo2026", "（招待コードは講座内で配布）"),
    # 運営者個人の"専用台本スキル"への参照（使い分けリスト等）→ 一般語
    ("eekanji-kenji-script", "〔発信者専用の台本スキル〕"),
    ("desse-reel-script", "〔発信者専用の台本スキル〕"),
    ("daihon-otobana", "〔発信者専用の台本スキル〕"),
    ("otobana", "〔アカウント例〕"),
    ("daihon-eiga-vlog", "〔発信者専用の台本スキル〕"),
    # 個人・ブランド名 → 一般語
    ("THE OTOGIBANASHI SUPPLY", "〔ブランド名〕"),
    ("OTOGIBANASHI", "〔ブランド名〕"),
    ("おとばな", "〔ブランド名〕"),
    ("お揃い服ブランド", "〔自分のジャンル〕"),
    ("いい感じケンジ", "〔アカウント例〕"),
    ("eekanji_kenji", "〔アカウント例〕"),
    ("eekanji", "〔アカウント例〕"),
    ("desse", "〔アカウント例〕"),
    ("kanako_vlog", "〔参考アカウント〕"),
    ("kanako", "〔参考アカウント〕"),
    ("かなこ", "〔発信者例〕"),
    # 大阪弁Vlogの参考話者（名前だけ伏せる。台本本文は残す）
    ("華月", "〔話者名〕"),
    ("@kiiiiiii0228", "〔参考アカウント〕"),
    ("kiiiiiii0228", "〔参考アカウント〕"),
    # 参考教材の発信者名（genre-sentei由来。教材名ごと一般化）
    ("なるさん「ショート動画の教科書」", "参考教材"),
    ("ショート動画の教科書", "参考教材"),
    ("・なる式", ""),                       # 「（日付・なる式）」等の丸カッコ内の付記ごと消す
    ("なる式バズリサーチ", "バズリサーチの定石"),
    ("なる式", "参考教材"),
    ("なるさんは実際にした", "実際に行われた判断"),
    ("なるさん自身も", "参考教材でも"),
    ("なるさんの実例", "参考教材の実例"),
    ("なるさんの新垢と同じ判断", "参考教材と同じ判断"),
    ("なるさん本人", "参考教材の発信者"),
    ("なるさんも", "参考教材でも"),
    ("なるさん", "参考教材の発信者"),
    # 添削の実例アンカーに出る第三者アカウント（実在の個人。受講生向けには伏せる。
    # 数字と構造は教材として残し、誰の投稿かだけ分からなくする）
    ("「オバ美・第1話」（@obami30_beauty）", "「産後ママの自分磨き連載・第1話」（実例）"),
    ("@obami30_beauty", "〔実例アカウント〕"),
    ("obami30_beauty", "〔実例アカウント〕"),
    ("オバ美", "〔実例アカウント〕"),
    # 運営者自身の呼称
    ("けんじさん", "運営者"),
    # 個人の絶対パス
    ("/Users/miyabekenji", "~"),
]

# 一般化後に「残っていたら人の確認が要る」語。1つでも残れば commit を止める。
# （REPLACEMENTSで拾い切れなかった新しい変種を検知する番人）
REVIEW_TERMS = [
    "otolabo", "おとばな", "OTOGIBANASHI", "華月", "kiiiiiii", "kanako",
    "/Users/miyabekenji", "eekanji", "desse", "otobana",
    # 他社ブランド名（受講生向けに出さない。concept-brush-up由来）
    "SAKIYOMI", "先読み",
    # 参考教材の発信者名（genre-sentei由来）
    "なるさん", "naruwork", "ショート動画の教科書",
    # 添削の実例アンカーに出る第三者アカウント（実在の個人。変種が増えたら検知して止める）
    "obami30", "オバ美",
    # 運営者のパソコンにしか無い書き癖チェック一式（受講生の手元では動かない。
    # 節の置き換え漏れ・節の外に書き足された参照を検知して止める）
    "kakikuse", "~/.claude/tools", ".claude/tools", "catalog/",
]

# 「## 出す前の書き癖チェック」節の受講生向け正本
KAKIKUSE_TEMPLATE = REPO / "templates" / "kakikuse_jukousei.md"
KAKIKUSE_HEADING = "## 出す前の書き癖チェック"
KAKIKUSE_SLOT = "{{点検する文}}"
KAKIKUSE_DEFAULT_TARGET = "このスキルが作って渡す文章"

TEXT_EXTS = {".md", ".html", ".json", ".py", ".sh", ".txt", ".ps1", ".js"}


def sh(*args, **kw):
    return subprocess.run(args, cwd=REPO, text=True, capture_output=True, **kw)


def copy_skill(name):
    src, dst = SKILLS_SRC / name, DEST / name
    if not src.is_dir():
        print(f"  ⚠️ 原本が無い: {src}（スキップ）")
        return False
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".DS_Store",
        # 他社記事（SAKIYOMI 50コンセプト）の要約は公開リポジトリに含めない
        "50-concepts-list.md", "evals"))
    return True


def load_kakikuse_template():
    """正本を読み、(節の本文, {スキル名: 点検する文}) を返す。
    正本の下の <!-- ===== ... --> 以降はスキルごとの対応表で、配布版には写さない。"""
    if not KAKIKUSE_TEMPLATE.is_file():
        print(f"⛔ 書き癖チェックの正本が無い: {KAKIKUSE_TEMPLATE}")
        sys.exit(1)
    text = KAKIKUSE_TEMPLATE.read_text(encoding="utf-8")
    marker = "<!-- ====="
    body, _, table = text.partition(marker)
    body = body.strip() + "\n"
    if not body.startswith(KAKIKUSE_HEADING) or KAKIKUSE_SLOT not in body:
        print(f"⛔ 正本の形が違う（先頭が「{KAKIKUSE_HEADING}」で、{KAKIKUSE_SLOT} を含むこと）")
        sys.exit(1)
    targets = {}
    for line in table.splitlines():
        name, sep, target = line.partition(":")
        if sep and name.strip() and " " not in name.strip() and target.strip():
            targets[name.strip()] = target.strip()
    return body, targets


def replace_kakikuse_section(name, body, targets):
    """配布版 SKILL.md の書き癖チェック節を正本に置き換える。置き換えた数を返す。"""
    f = DEST / name / "SKILL.md"
    if not f.is_file():
        return 0
    lines = f.read_text(encoding="utf-8").split("\n")
    out, count, i = [], 0, 0
    while i < len(lines):
        if lines[i].startswith(KAKIKUSE_HEADING):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("## "):
                j += 1
            target = targets.get(name)
            if target is None:
                print(f"     （{name} の点検する文が正本に無いので共通の文を入れました）")
                target = KAKIKUSE_DEFAULT_TARGET
            section = body.replace(KAKIKUSE_SLOT, target)
            while out and out[-1] == "":
                out.pop()
            out += ["", *section.rstrip("\n").split("\n"), ""]
            count += 1
            i = j
        else:
            out.append(lines[i])
            i += 1
    if count:
        f.write_text("\n".join(out).rstrip("\n") + "\n", encoding="utf-8")
    return count


def genericize(name):
    for f in (DEST / name).rglob("*"):
        if f.is_file() and f.suffix in TEXT_EXTS:
            try:
                s = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, IsADirectoryError):
                continue
            t = s
            for before, after in REPLACEMENTS:
                t = t.replace(before, after)
            if t != s:
                f.write_text(t, encoding="utf-8")


def scan_review():
    hits = []
    for f in DEST.rglob("*"):
        if f.is_file() and f.suffix in TEXT_EXTS:
            try:
                lines = f.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, IsADirectoryError):
                continue
            for i, line in enumerate(lines, 1):
                for term in REVIEW_TERMS:
                    if term in line:
                        hits.append((f.relative_to(REPO), i, term, line.strip()[:80]))
    return hits


def main():
    args = sys.argv[1:]
    do_commit = "--commit" in args or "--push" in args
    do_push = "--push" in args

    kakikuse_body, kakikuse_targets = load_kakikuse_template()
    print(f"同期: {SKILLS_SRC} → {DEST}")
    for name in SKILLS:
        if copy_skill(name):
            n = replace_kakikuse_section(name, kakikuse_body, kakikuse_targets)
            genericize(name)
            print(f"  ✓ {name}" + ("（書き癖チェックを受講生向けに置き換え）" if n else ""))

    print("\n危険語チェック（人の確認が要る語が残っていないか）...")
    hits = scan_review()
    if hits:
        print(f"  ⛔ {len(hits)}件、確認が必要な語が残っています。commitを中止します:")
        for rel, ln, term, preview in hits[:40]:
            print(f"     {rel}:{ln}  [{term}]  {preview}")
        print("\n  → 上を確認し、REPLACEMENTS にルールを足すか、手で直してから再実行してください。")
        print("     （どうしてもこのまま出す場合は手動で git add/commit してください）")
        sys.exit(1)
    print("  ✓ 危険語なし")

    sh("git", "add", "-A")
    diff = sh("git", "diff", "--cached", "--stat").stdout.strip()
    if not diff:
        print("\n変更なし（お店は最新の状態です）。")
        return
    print("\n変更ファイル:\n" + diff)

    if do_commit:
        sh("git", "commit", "-m", "sync: 原本スキルの更新を反映")
        print("✓ コミットしました")
        if do_push:
            r = sh("git", "push", "origin", "main")
            print("✓ push 完了" if r.returncode == 0 else "⚠️ push失敗:\n" + r.stderr)
    else:
        print("\nstage済み。問題なければ:")
        print("  python3 sync.py --commit   # コミットのみ")
        print("  python3 sync.py --push     # コミット＋公開反映")


if __name__ == "__main__":
    main()
