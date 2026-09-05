---
name: stories-save
description: "【ストーリー自動保存】指定したInstagramアカウントのストーリーを、毎朝決まった時刻にパソコンが自動で保存するスキル（Mac/Windows両対応・拡張機能不要・無料）。ブラウザのログイン情報を借りてストーリーの元データを直接取り込み、画像は原寸のまま、動画は1コマ目の静止画として保存する（動画のMP4は容量が重くなるため保存しない）。1日分は『26.9.4.jpg』という1枚の画像に並べてまとめられ、フォルダは月ごとに整理される。時刻・リンクスタンプのURL・アンケート・質問箱・音楽・再シェアもJSONに残る。一度設定すればClaudeを開いていなくても毎朝勝手に走り、朝9時にパソコンが閉じていてもその日のうちに開けば自動で拾う。『ストーリーを毎日保存して』『ストーリー保存を設定して』『毎朝ストーリーを自動で保存したい』『このアカウントのストーリーを保存して』『ストーリー保存に追加して』『ストーリー保存できてる？』『先週のストーリーを見せて』『今月のストーリーを振り返りたい』『ストーリー保存が止まってる』『ストーリーの自動保存を止めて』『ストーリー保存をやめたい』『stories-save』などのフレーズで必ず起動すること。保存したいアカウントのURLやIDを渡されて『毎日/自動で/毎朝』と言われた場合は常にこのスキルを使う。※保存したストーリーの中身を分解して構成・デザインのお手本にするのは stories-bunseki（このスキルの出力がそのまま入力になる）。自分のストーリーズの文面を作るのは stories-days / stories-launch / stories-affiliate。リールの保存・分析は bunseki-reel / bunseki-competitor-account。"
---

# ストーリー自動保存（stories-save）

指定したアカウントのInstagramストーリーを、**毎朝パソコンが勝手に保存する**。
Claude Codeが要るのは最初の設定のときだけ。動き出したあとは開いていなくてよい。

## 何が保存されるか

```
~/Documents/Claude/Projects/ストーリー保存/
├ _設定.json                            見るアカウントとログイン元
├ _ログ.txt                             いつ何枚保存したか
└ <アカウント名>/2026年/9月/
   ├ 26.9.4.jpg                        ★その日に取れたストーリーを並べた1枚（これを見る）
   └ 26.9.4/                           元データ
      ├ 26.9.4-1.jpg … 画像は原寸、動画は1コマ目の静止画
      └ info.json    … 時刻・リンク先URL・アンケート・質問箱・音楽・再シェア
```

- **動画のMP4は保存しない**（毎日ためると重くなるため）。動画は静止画1枚＋秒数だけ残す
- ストーリーは24時間残るので、**その日のうちに一度パソコンを開けば取りこぼさない**
- **フォルダとファイル名は「保存した日」で決まる**（投稿された日ではない）。9/4の朝に走れば、前の晩に出たストーリーも `26.9.4` に入る
- 1枚ものの中は**投稿された時刻順**に並ぶ。前日の投稿は `9/3 21:27` のように日付付きで表示される

## 大事な前提（最初に必ず伝える）

- **ブラウザでインスタにログインしたままにしておくこと。** ログインが切れると止まる
- **アカウントが制限されるリスクがある。** Instagramは自動での情報収集を規約違反としている（<https://help.instagram.com/740480200552298/>）。**メインではなくサブのアカウントでログインした状態で使うことを勧める。**このリスクは受講生に必ず伝える
- **閲覧者リストに載るかどうかは保証できない。** この方式は元データを取りに行くだけで「見ました」の通知は送っていないが、**何をすると閲覧者リストに載るのかはInstagramが公表しておらず、こちらでも検証していない。**「バレません」と言い切らないこと
- **非公開アカウントは、こちらがフォローして承認されている必要がある**
- 保存したものは自分の研究・分析用。**再配布しない**

---

## STEP 0：セットアップ（初回だけ）

```bash
python3 <skill>/scripts/setup.py     # Windowsは python <skill>\scripts\setup.py
```

**前提: Python 3.9+ が入っていること。** Windowsの受講生は入っていないことが多い。
python.org からのインストールを案内し、**「Add python.exe to PATH」にチェックを入れる**ことを必ず伝える。
Macで「コマンドラインデベロッパツールをインストールしますか？」が出たら「インストール」を押してもらう。

- `~/.bunseki-tools/venv`（他の分析スキルと共通）に yt-dlp と Pillow を入れるだけ。**Homebrew も ffmpeg も不要**
- 最後に出る `✅ セットアップ完了。以下の python で実行してください: <venv-python>` のパスを控える。**以降のスクリプトは必ずこの venv python で実行する**
  - Mac: `~/.bunseki-tools/venv/bin/python`
  - Windows: `%USERPROFILE%\.bunseki-tools\venv\Scripts\python.exe`
- OSは `setup.py` の出力（`OS: ...`）で分かる

### ⚠ WindowsでChromeを使っている場合（ここだけ分岐する）

WindowsのChrome系ブラウザは Chrome 127以降、ログイン情報を外部から読み取れない仕組みに変わった（App-Bound Encryption。yt-dlp側も対応予定なしと公言）。**Windowsの人には最初に使っているブラウザを聞くこと。**

| 使っているブラウザ | やること |
|---|---|
| Mac + Chrome / Firefox / Edge | そのままでOK（初回だけキーチェーンの許可を求められる。**「常に許可」を押してもらう**。「許可」だけだと毎回聞かれて自動実行が止まる） |
| Mac + Safari | **追加設定が必要**。システム設定→プライバシーとセキュリティ→フルディスクアクセスでターミナル/Claude Codeをオン。**面倒なのでChromeかFirefoxを勧める** |
| Windows + Firefox | そのままでOK（`--cookies-from firefox`） |
| **Windows + Chrome / Edge / Brave / Opera / Vivaldi** | **A か B のどちらかが必要**（下記） |

- **A: Firefoxを使う** … Firefoxでインスタにログインしてもらい `--cookies-from firefox`
- **B: Cookieを1回書き出す** … Chrome拡張『Get cookies.txt LOCALLY』でインスタを開いた状態でエクスポート →
  `--cookies-file "C:\Users\xxx\Downloads\instagram.com_cookies.txt"` を指定。数か月に一度取り直す

## STEP 1：見るアカウントを登録する

保存したいアカウントを聞く（IDでもプロフィールURLでも可・複数可）。

```bash
<venv-python> <skill>/scripts/add_account.py <ユーザー名 or URL> [...]
<venv-python> <skill>/scripts/add_account.py --list                  # 一覧
<venv-python> <skill>/scripts/add_account.py --remove <ユーザー名>    # 削除
<venv-python> <skill>/scripts/add_account.py --cookies-from firefox  # ログイン元の変更
```

- ここでだけアカウントIDを問い合わせる（毎朝の保存では一切呼ばない）
- `❌ @xxx が見つかりませんでした` が出たら、つづり・非公開・時間をあけて再実行、の3つを案内する
- **ここまで来たら一度ユーザーに登録内容を見せて確認する**

## STEP 2：手で1回動かして、実物を見せる

```bash
<venv-python> <skill>/scripts/save_stories.py --force
```

- `@xxx: 表示中 N枚 / 新しく保存 N枚` と `1枚ものを更新: 26.9.4.jpg` が出れば成功
- **できあがった `26.9.4.jpg` を必ず開いて見せる**（`open` / `start`）。ここを飛ばさない
- 相手が今ストーリーを出していないと0枚になる。そのときは「今は出ていないだけ」と伝えて、翌朝の自動実行に任せる

## STEP 3：毎朝の自動実行を登録する

```bash
<venv-python> <skill>/scripts/install_schedule.py              # 登録
<venv-python> <skill>/scripts/install_schedule.py --status     # 動いているか確認
<venv-python> <skill>/scripts/install_schedule.py --uninstall   # 解除
```

- Mac は launchd、Windows はタスクスケジューラに登録する（**9:00 / 9:30 / 10:30 / 12:00 / 15:00 / 19:00** の6回）
- Mac: スリープ中に来た回は**復帰時にまとめて1回**実行される（man launchd.plist）。**電源オフだった回は実行されない**
- Windows: 見逃した回は起動後に走るが、**既定で10分ほど遅れる**（Microsoftの仕様）
- その日すでに成功していれば即終了するので、**実際に保存が走るのは1日1回だけ**
- 朝9時にパソコンが閉じていても、その日のどこかで開けば拾う
- **登録したら `--status` まで実行して、登録されていることを確認してから完了と言う**

## STEP 4：振り返り（頼まれたときだけ）

```bash
<venv-python> <skill>/scripts/make_review.py --days 7        # 直近1週間
<venv-python> <skill>/scripts/make_review.py --month 2026-09 # 9月ぜんぶ
<venv-python> <skill>/scripts/make_review.py --days 7 --account xxx
```

日付ごとに1枚ものを並べ、リンク先URL・アンケート・質問箱の中身を書き出したHTMLを作ってブラウザで開く。
**毎日は作らない。**「先週のストーリー見せて」「今月分まとめて」と言われたときだけ。

---

## 保存できているか聞かれたとき

1. `_ログ.txt` の末尾を見る（いつ何枚保存したか）
2. `⚠_保存に失敗しました.txt` があれば、その中身が原因と直し方
3. `install_schedule.py --status` で自動実行が生きているか

よくある止まり方は**ログイン切れ**。ブラウザでインスタを開き直してもらい、`save_stories.py --force` でやり直す。
他の詰まりどころは `references/troubleshooting.md`。

## やらないこと

- **動画のMP4は保存しない**（容量のため。必要なら bunseki-reel を使う）
- **相手のストーリーに反応を返さない**（閲覧・保存だけ。DM・スタンプ・投票はしない）
- **保存したものを人に配らない**
- 1日に何度も取りに行かない（成功したらその日は終わり）
