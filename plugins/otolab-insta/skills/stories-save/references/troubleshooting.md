# stories-save 困ったとき

## ログイン情報が取れない

| 症状 | 原因 | 直し方 |
|---|---|---|
| `chrome にInstagramのログイン情報が見つかりませんでした` | そのブラウザでインスタにログインしていない | ブラウザでインスタを開いてログイン → もう一度 |
| Windowsで同じエラーが消えない | **Chrome 127以降のWindowsのChrome系（Chrome/Edge/Brave/Opera/Vivaldi）は外部からCookieを読めない**（App-Bound Encryption。突破不可） | `--cookies-from firefox` にする、または『Get cookies.txt LOCALLY』で書き出して `--cookies-file` を指定 |
| `Instagramに拒否されました` | ログインが切れた／別端末でログインし直した | ブラウザでインスタを開き直して `save_stories.py --force` |

Macで `chrome` を指定するとキーチェーンの許可を求められることがある。**「常に許可」を押してもらう**（「許可」だけだと毎回聞かれ、留守中の自動実行が黙って失敗する）。

MacのSafariのCookieを読むには「フルディスクアクセス」の許可が要る。面倒なのでChromeかFirefoxを勧める。

## アカウントが見つからない

- つづり違い（プロフィールURLの `instagram.com/` のうしろの文字が正解）
- 非公開アカウント → こちらがフォローして**承認されている**必要がある
- 立て続けに実行すると一時的に断られる（429）。**5〜10分あけて**再実行

## 0枚しか保存されない

- 相手がその時点でストーリーを出していないだけ。翌朝の自動実行に任せる
- ストーリーは24時間で消える。**前日の朝より前**に投稿されて消えたものは取れない
- ハイライトは対象外（このスキルは「今出ているストーリー」だけを見る）

## 毎朝動いていない

```bash
<venv-python> <skill>/scripts/install_schedule.py --status
```

- **未登録です** → `install_schedule.py` で登録し直す
- Mac: パソコンが**電源オフ**だと動かない（スリープなら開いたときに走る）
- Windows: タスクスケジューラの「実行できなかったタスクをすぐに開始する」を使っている。パソコンを起動したあと**10分ほど待ってから**走る（Microsoftの既定の遅延）。すぐ動かしたいときは `save_stories.py --force`
- `_ログ_自動実行.txt` に自動実行のときの出力が残る

## 画像の中の文字がおかしい / 豆腐（□）になる

日本語フォントが見つかっていない。`story_core.py` の `_FONT_CANDIDATES` に、そのパソコンにあるフォントのパスを足す。

## 保存が重くなってきた

`_設定.json` の `keep_months` に数字を入れると、それより古い月フォルダを自動で消す（例: `12` なら12か月より前を削除）。既定の `0` は消さない。

## 手で1日分だけ取り直したい

```bash
<venv-python> <skill>/scripts/save_stories.py --force              # 全部
<venv-python> <skill>/scripts/save_stories.py --force --account xx # 1アカウントだけ
```

すでに保存済みの枚は二重に増えない（IDで判定している）。
