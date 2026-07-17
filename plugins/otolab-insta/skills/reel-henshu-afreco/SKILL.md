---
name: reel-henshu-afreco
description: アフレコ音声から縦型ショート動画を自動編集する
argument-hint: [project]
allowed-tools: [Bash, Read, Write]
version: 2.0.0
---

# ショート動画自動編集スキル

アフレコ音声を提出するだけで、Whisper文字起こし → カード生成 → 素材自動選定 → エディタ起動まで一気に行うスキル。

## スクリプトの場所

```
~/reel-henshu-afreco/scripts/
```

実行には必ず `~/reel-henshu-afreco/venv/bin/python3` を使うこと（システムpython3ではjanome/mlx_whisperが入っていないため動かない）。

> **⚠️ ローカルMacに触れる Claude Code 環境で実行すること**
> このスキルはローカルMac内のファイル（`~/reel-henshu-afreco`）を操作し、ffmpeg・Whisperをローカル実行する。次のいずれかで動く：**①ターミナルの `claude` コマンド**、または **②Claudeデスクトップアプリの「Code」モード（ローカルフォルダを開いた状態）**。
> **ブラウザ版（claude.ai）・Chat/Coworkモード・サンドボックス/クラウドセッションでは動作しない**（`~/` 以下が見えず「サンドボックス環境にツールが無い」となる）。「サンドボックス」という表示が出たら、Codeモードかターミナルで開き直すこと。
>
> **動作環境**: 現状 **Apple Silicon (M1〜M4) の Mac 向け**。動画処理のコード自体は Windows にも対応済み（faster-whisper）だが、このスキルの**自動セットアップ（Homebrew / install.sh）が Mac 向け**のため、当面は Mac で使う。Windows での自動フローは準備中。

---

## 📋 事前準備（受講生に必ず伝えること）

初めて使う前に、以下を済ませておくとスムーズ：

1. **Homebrew を先に入れておく**
   `install.sh` は ffmpeg のインストールに Homebrew を使う。**未導入だと `brew install ffmpeg` のところで止まる**。入れ方は下の「Homebrew の入れ方」を参照。
2. **初回は時間がかかる（ネット接続必須）**
   - セットアップ（`install.sh`）＝依存パッケージのダウンロードで**数分**
   - 最初の動画ビルド時に、文字起こしモデル（Whisper、**約1.5GB**）を自動ダウンロードするため**十数分**かかることがある（2回目以降はキャッシュされて速い）
3. **Apple Silicon Mac（M1〜M4）であること**を確認しておく。

### Homebrew の入れ方

まず入っているか確認する（バージョンが出れば導入済み。この手順は不要）：

```bash
brew --version
```

`command not found` と出たら未導入。以下で入れる。

**① Mac標準の「ターミナル」アプリを開き、次のコマンドを貼り付けて実行**（公式インストーラ）：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

- 途中で **Macのログインパスワード**を求められる（打っても画面には表示されない。そのままEnter）
- Xcodeの部品が必要な場合は自動で入る。数分かかる。

**② インストール後、`brew` コマンドを使えるようにする**（Apple Silicon Macで必要な設定。ここを忘れると「入れたのに brew が見つからない」となる）：

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

**③ 確認**：

```bash
brew --version
```

バージョン（例: `Homebrew 4.x.x`）が表示されればOK。これで STEP 0 のセットアップに進める。

---

## 実行フロー

### STEP 0：初回セットアップ（`~/reel-henshu-afreco` が無いとき）

`~/reel-henshu-afreco/scripts/build_shorts.py` が存在するか確認する：

```bash
ls ~/reel-henshu-afreco/scripts/build_shorts.py
```

**存在する場合** → セットアップ済み。STEP 1 へ進む。

**存在しない場合** → 以下を順に実行してセットアップする。

まず前提ソフト（Homebrew・git）があるか確認する：

```bash
command -v brew && command -v git && echo "OK: 前提ソフトあり"
```

- `git` が無い → `xcode-select --install` を案内する（ダイアログでインストール。完了後に再実行）
- `brew` が無い → [https://brew.sh](https://brew.sh) のコマンドでHomebrewを入れるよう案内する（**未導入のまま進めると `install.sh` が ffmpeg インストールで止まる**）

前提が揃ったら、リポジトリを取得してセットアップスクリプトを実行する：

```bash
git clone https://github.com/izzzenk-ops/reel-henshu-afreco.git ~/reel-henshu-afreco
cd ~/reel-henshu-afreco && ./install.sh
```

`install.sh` が行うこと：ffmpeg導入（未導入時）・venv作成・依存パッケージ（mlx-whisper / Pillow / janome）インストール・config.json生成・start.sh生成。**初回は依存パッケージのダウンロードで数分かかる**（ユーザーに待つよう伝える）。

> **効果音を使う場合**: `~/reel-henshu-afreco/config.json` の `sound_dir` を効果音フォルダのパスに書き換える（既定は同梱の空フォルダ `~/reel-henshu-afreco/sounds`）。効果音を使わなければ変更不要。

セットアップが終わったら STEP 1 へ進む。

---

### STEP 1：アフレコデータの受け取り

スキル起動時、まずユーザーに以下を聞く：

```
アフレコ音声ファイルのパスを教えてください。
（例: /Users/yourname/Desktop/voiceover.m4a）
```

ファイルが存在するか確認する。存在しない場合はパスを再確認する。

---

### STEP 2：素材フォルダとプロジェクト名の受け取り

次に以下を聞く：

```
素材フォルダのパスとプロジェクト名を教えてください。

・素材フォルダ（mp4が入っているフォルダ）のパス
  例: /Volumes/SSD/my_project/materials
  
・プロジェクト名（英数字・アンダースコア推奨）
  例: my_project
```

---

### STEP 3：素材タグ付けの確認

`~/reel-henshu-afreco/work/<project>/materials.json` が存在するか確認する。

```bash
ls ~/reel-henshu-afreco/work/<project>/materials.json
```

**存在しない場合** → タグ付けが必要。以下を実行してからユーザーに報告する：

```bash
~/reel-henshu-afreco/venv/bin/python3 ~/reel-henshu-afreco/scripts/tag_materials.py init \
  "<素材フォルダ>" \
  ~/reel-henshu-afreco/work/<project>
```

実行後、`materials.json` の各クリップに `tag`（person/landscape/either）と `memo`（内容説明）を埋める必要がある。Claudeが `frames/` 内のフレーム画像を見てタグ付けを行う。

**存在する場合** → タグ付け済みとみなしてSTEP 4へ進む。

---

### STEP 4：ビルド実行

```bash
~/reel-henshu-afreco/venv/bin/python3 ~/reel-henshu-afreco/scripts/build_shorts.py \
  "<素材フォルダ>" \
  --project "<project>" \
  --voiceover "<アフレコファイル>"
```

処理内容（ログで確認できる）：
1. アフレコ無音カット → Whisper文字起こし → カード生成
2. カードのセリフと素材タグ/memoを照合して最適クリップを自動選定
3. final.mp4 を書き出し

完了したらカード数・再生時間をユーザーに報告する。

> **手動割り当てフロー（カードだけ先に作る）**
> ユーザーが「映像は自分で割り当てる」「素材は後から入れる」「タグ付け不要」と言った場合は、
> タグ付け（STEP 3）を丸ごとスキップし、`--cards-only` を付けてビルドする：
>
> ```bash
> ~/reel-henshu-afreco/venv/bin/python3 ~/reel-henshu-afreco/scripts/build_shorts.py \
>   "<素材フォルダ>" --project "<project>" --voiceover "<アフレコ>" --cards-only
> ```
>
> 全カードが未割当てで生成される。素材はエディタの「🔄 動画素材フォルダを更新」ボタンで
> いつでも取り込める（フォルダへの追加・削除を自動で同期。動画のほか jpg/png/HEIC画像も可）。
> ユーザーは各カードのプルダウンから素材を選んで割り当てる。

---

### STEP 5：エディタを開く

```bash
kill $(lsof -ti :8766) 2>/dev/null
~/reel-henshu-afreco/venv/bin/python3 ~/reel-henshu-afreco/scripts/editor_server.py <project> &
sleep 1
open http://localhost:8766
```

ユーザーに伝える：

```
エディタを http://localhost:8766 で開きました。

エディタでできること：
・各カードの映像を確認・差し替え
・テキスト編集
・効果音の追加（サウンドフォルダから選択）
・トリム（in点調整）
・今すぐ更新するボタンで動画を再生成
・完成版を確認ボタンでプレビュー
```

---

## よくあるエラーと対処

| エラー | 原因 | 対処 |
|---|---|---|
| `materials.json が見つかりません` | タグ付け未実施 | STEP 3 の `tag_materials.py init` を実行 |
| `タグ付けされていません` | tag/memo が null のクリップあり | materials.json を開いてタグを埋める |
| `mlx_whisper` エラー | venv外のpythonで実行している | `~/reel-henshu-afreco/venv/bin/python3` を使う |
| エディタが開かない | ポート8766が使用中 | `kill $(lsof -ti :8766)` してから再起動 |
| 効果音が表示されない | config.json の sound_dir が未設定 | `~/reel-henshu-afreco/config.json` を確認 |

---

## テロップのスタイル変更

`~/reel-henshu-afreco/scripts/captions.py` で管理。変更後は必ずサーバーを再起動すること（モジュールキャッシュのため）。変更時は `TELOP_STYLE_VERSION` も更新するとキャッシュが自動無効化される。

| 設定 | 定数名 |
|---|---|
| フォントサイズ | `TELOP_FONTSIZE` |
| 縦位置オフセット | `TELOP_Y_OFFSET` |
| スタイルバージョン | `TELOP_STYLE_VERSION` |

---

## ファイル構成

```
~/reel-henshu-afreco/
├── scripts/
│   ├── build_shorts.py      # メインCLI（アフレコ → 動画）
│   ├── tag_materials.py     # 素材フレーム抽出・タグ付け
│   ├── assign_clips.py      # カード↔素材の自動マッチング
│   ├── pacing.py            # Whisper文字起こし・カード生成
│   ├── render.py            # 動画レンダリング（差分キャッシュ）
│   ├── captions.py          # テロップ生成（PIL + ffmpeg）
│   ├── editor_server.py     # エディタサーバー（port 8766）
│   └── _vendor/             # 同梱ライブラリ（変更不要）
├── editor/
│   └── index.html           # ブラウザエディタ
├── sounds/                  # 効果音フォルダ（config.jsonで変更可）
├── venv/                    # Python仮想環境（install.shが自動生成）
├── config.json              # ローカル設定（sound_dir等）
├── install.sh               # セットアップスクリプト
├── start.sh                 # エディタ起動スクリプト（install.shが生成）
└── work/
    └── <project>/
        ├── materials.json   # 素材タグ情報
        ├── timeline.json    # カード・タイムライン
        ├── final.mp4        # 書き出し済み動画
        └── render_cache/    # ユニット差分キャッシュ
```
