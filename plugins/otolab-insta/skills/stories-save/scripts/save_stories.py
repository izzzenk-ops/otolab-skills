#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""登録したアカウントのストーリーを保存する（毎朝これが自動で走る）。

  通常:      python save_stories.py
  やり直し:  python save_stories.py --force        （その日すでに成功していても実行する）
  1件だけ:   python save_stories.py --account xxx

保存されるもの（動画の実物MP4は保存しない）:
  <保存先>/<アカウント>/2026年/9月/26.9.4.jpg      ← その日の全ストーリーを並べた1枚
  <保存先>/<アカウント>/2026年/9月/26.9.4/         ← 元データ
        26.9.4-1.jpg … 画像は原寸、動画はその1コマ目
        info.json    … 時刻・リンク先URL・アンケート・音楽など
"""
import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from story_core import (IG, StoryError, _pick_image, base_dir, build_contact_sheet,  # noqa: E402
                        day_paths, fetch_story_items, get_cookies, item_meta, load_config,
                        load_state, log, notify, save_state)

ALERT_NAME = "⚠_保存に失敗しました.txt"


def day_info_path(day_dir: Path) -> Path:
    return day_dir / "info.json"


def load_day(day_dir: Path) -> dict:
    p = day_info_path(day_dir)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"items": []}


def rebuild_day(username: str, dt: datetime) -> int:
    """その日のファイル名を時刻順に振り直して、1枚ものを作り直す。"""
    sheet, day_dir, stem = day_paths(username, dt)
    info = load_day(day_dir)
    items = sorted(info.get("items", []), key=lambda e: e.get("taken_at", 0))
    if not items:
        return 0

    # いったん退避してから正式名にする（連番がずれても衝突しない）
    for i, e in enumerate(items):
        cur = day_dir / (e.get("file") or "")
        if e.get("file") and cur.exists():
            tmp = day_dir / f"__tmp{i}.jpg"
            cur.rename(tmp)
            e["file"] = tmp.name
    for i, e in enumerate(items):
        want = f"{stem}-{i + 1}.jpg"
        cur = day_dir / (e.get("file") or "")
        if e.get("file") and cur.exists():
            cur.rename(day_dir / want)
            e["file"] = want
        else:
            e["file"] = None

    info.update({"account": username, "date": dt.strftime("%Y-%m-%d"),
                 "count": len(items), "items": items})
    day_info_path(day_dir).write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    build_contact_sheet(items, day_dir, sheet, username, dt)
    return len(items)


def cleanup(cfg):
    """keep_months が設定されていれば、古い月フォルダを消す。既定(0)では何もしない。"""
    keep = int(cfg.get("keep_months") or 0)
    if keep <= 0:
        return
    if keep < 3:
        log(f"keep_months={keep} は消しすぎるので無視しました（3以上で有効）")
        return
    import shutil
    today = date.today()
    limit = today.year * 12 + today.month - keep
    for acc in cfg["accounts"]:
        adir = base_dir() / acc["username"]
        for ydir in sorted(adir.glob("*年")):
            for mdir in sorted(ydir.glob("*月")):
                try:
                    y = int(ydir.name[:-1]); m = int(mdir.name[:-1])
                except ValueError:
                    continue
                if y * 12 + m < limit:
                    shutil.rmtree(mdir, ignore_errors=True)
                    log(f"古い月を削除: {mdir}")
            if not any(ydir.iterdir()):
                ydir.rmdir()


def run(args) -> int:
    cfg = load_config()
    if not cfg.get("accounts"):
        raise StoryError("保存するアカウントがまだ登録されていません。\n"
                         "  add_account.py で登録してください。")

    accounts = cfg["accounts"]
    if args.account:
        want = args.account.lstrip("@").lstrip("＠").lower()
        accounts = [a for a in accounts if a["username"].lower() == want]
        if not accounts:
            raise StoryError(f"@{want} は登録されていません。")

    st = load_state()
    today = date.today().isoformat()
    if st.get("last_success") == today and not args.force:
        log("本日分は保存済みのため何もしません（やり直すなら --force）")
        return 0

    saved_on = datetime.now()          # フォルダ・ファイル名はこの「保存した日」で決める
    ig = IG(get_cookies(cfg))
    saved_ids = st.setdefault("saved_ids", {})
    new_total, failed_total, affected = 0, 0, {}

    for i, acc in enumerate(accounts):
        username = acc["username"]
        if i:
            time.sleep(3)   # 立て続けに叩かない
        items, _user = fetch_story_items(ig, acc["user_id"])
        history = list(saved_ids.get(username, []))
        seen = set(history)
        added, failed = 0, 0

        for item in items:
            meta = item_meta(item)
            if not meta["id"] or meta["id"] in seen or not meta["taken_at"]:
                continue
            _sheet, day_dir, _stem = day_paths(username, saved_on)
            day_dir.mkdir(parents=True, exist_ok=True)

            cand = _pick_image(item)
            if not cand:
                log(f"  画像が取れませんでした: @{username} {meta['id']}")
                failed += 1
                continue
            try:
                blob = ig.blob(cand["url"])
            except Exception as e:
                log(f"  ダウンロード失敗（今日のうちにやり直します）: @{username} {meta['id']} {e}")
                failed += 1
                continue
            tmp = day_dir / f"__new_{meta['id']}.jpg"
            tmp.write_bytes(blob)
            meta["file"] = tmp.name
            meta["width"] = cand.get("width")
            meta["height"] = cand.get("height")

            info = load_day(day_dir)
            existing = info.setdefault("items", [])
            if any(str(x.get("id")) == meta["id"] for x in existing):
                # 台帳が壊れて記憶を失っていても、同じ枚を二重に積まない
                tmp.unlink(missing_ok=True)
                seen.add(meta["id"])
                if meta["id"] not in history:
                    history.append(meta["id"])
                continue
            existing.append(meta)
            day_info_path(day_dir).write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

            seen.add(meta["id"])
            history.append(meta["id"])
            affected[(username, saved_on.year, saved_on.month, saved_on.day)] = True
            added += 1

        saved_ids[username] = history[-2000:]   # 古い順のまま切る（setにすると当日分が消える）
        new_total += added
        failed_total += failed
        log(f"@{username}: 表示中 {len(items)}枚 / 新しく保存 {added}枚"
            + (f" / 取れなかった {failed}枚" if failed else ""))

    for (username, y, m, dd) in affected:
        n = rebuild_day(username, datetime(y, m, dd))
        sheet, _d, _s = day_paths(username, datetime(y, m, dd))
        log(f"1枚ものを更新: {sheet.name}（{n}枚） → {sheet.parent}")

    st["last_run"] = datetime.now().isoformat(timespec="seconds")
    if failed_total:
        # 今日のうちに次の回でやり直す（ストーリーは24時間で消えるため後回しにしない）
        log(f"⚠ {failed_total}枚が取れませんでした。次の時刻にもう一度取りに行きます。")
    else:
        st["last_success"] = today
    save_state(st)
    cleanup(cfg)

    if not failed_total:
        alert = base_dir() / ALERT_NAME
        if alert.exists():
            alert.unlink()
    log(f"完了。新しく保存したのは {new_total}枚。")
    return 0 if not failed_total else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--account")
    args = ap.parse_args()
    try:
        return run(args)
    except StoryError as e:
        msg = str(e)
        log(f"❌ {msg}")
        try:
            p = base_dir() / ALERT_NAME
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"{datetime.now():%Y-%m-%d %H:%M} 保存できませんでした。\n\n{msg}\n\n"
                         "直したあと、Claudeに「ストーリー保存をやり直して」と言えば取り直せます。\n",
                         encoding="utf-8")
        except Exception:
            pass
        notify("ストーリー保存に失敗", msg.splitlines()[0][:120])
        return 1
    except Exception as e:  # 想定外
        log(f"❌ 想定外のエラー: {type(e).__name__}: {e}")
        notify("ストーリー保存に失敗", f"{type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
