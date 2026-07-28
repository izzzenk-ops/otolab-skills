---
name: cut-silence
description: 動画・音声の言葉と言葉の間（無音区間）を自動でカットして短くするスキル。Apple Silicon Macで自己完結（同梱スクリプト＋ffmpegのみ）。「間をカットして」「無音をカット」「言葉の間を切って」「動画を短くして」「無音部分を削って」「ジャンプカットして」「間を詰めて」「しゃべっていないところをカット」「cut-silence」などのフレーズで必ず起動すること。動画編集でテンポ改善・無音削除・間詰めを求められた場合は常にこのスキルを使うこと。
version: 1.0.0
allowed-tools: [Bash, Read]
---

# 無音カット（cut-silence）

動画・音声ファイルの「言葉と言葉の間」の無音区間を自動検出してカットし、テンポのよい素材に仕上げるスキル。
出力は元ファイルと同じフォルダに `元の名前_cut.mp4`（音声だけのファイルは `_cut.m4a`）で保存する。カット後の動画はそのままテロップ入れなど次の編集に回せる。

## このスキルについて

**受講生に配って同じ状態で使える自己完結型。** スクリプトはこのスキルに同梱済み（`<skill>/scripts/cut_silence.py`）で、pipの追加インストールは不要（Python標準ライブラリのみで動く）。必要なのは **ffmpeg だけ**。

- 使うツール: `ffmpeg` / `ffprobe`（無音検出・切り出し・結合）＋ Apple Silicon のハードウェアエンコード（`h264_videotoolbox`）で高速
- コスト **0円**（すべてローカルで完結・API課金なし）

## 前提条件

- **Apple Silicon Mac（M1〜M4）であること。** ハードウェアエンコーダ（h264_videotoolbox）を使うため、Intel Mac・Windowsは非対応。
- **ffmpeg が入っていること**（下のSTEP 0で自動チェック・未導入なら案内する）。
- ローカルMacに触れる Claude Code 環境で実行すること（ターミナルの `claude`、またはデスクトップアプリの「Code」モード）。ブラウザ版・サンドボックスでは `~/` 以下のファイルを触れないため動かない。

## デフォルト設定

| パラメータ | デフォルト | 意味 |
|---|---|---|
| `--noise` | -30 dB | 無音判定の閾値（小さいほど敏感） |
| `--min` | 0.3 秒 | この秒数以上の無音をカット（縦ショート最適値） |
| `--pad` | 0.08 秒 | カット前後に残すパディング（約2フレーム） |

---

## STEP 0：ffmpeg があるか確認する

まず ffmpeg / ffprobe が使えるか確認する（冪等・毎回流してよい）：

```bash
command -v ffmpeg && command -v ffprobe && echo "OK: ffmpeg あり"
```

**両方出た場合** → STEP 1 へ進む。

**`command not found` の場合** → Homebrew で ffmpeg を入れる。まず Homebrew があるか確認：

```bash
brew --version
```

- **`brew` があった場合**：`brew install ffmpeg` を実行（初回は数分かかる。ユーザーに待つよう伝える）。終わったら STEP 0 の確認をやり直す。
- **`brew` も無い場合**：Homebrew の導入から案内する。Mac標準の「ターミナル」で以下を実行してもらう（途中でMacのログインパスワードを求められる。打っても画面には出ないのでそのままEnter）：
  ```bash
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  ```
  インストール後、`brew` を使えるようにする（Apple Silicon Macで必要）：
  ```bash
  echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
  eval "$(/opt/homebrew/bin/brew shellenv)"
  ```
  そのあと `brew install ffmpeg` → STEP 0 の確認に戻る。

---

## STEP 1：ファイルを特定する

ユーザーが動画・音声ファイルのパスを伝えていない場合は確認する。
フォルダが指定された場合は中の動画ファイルを探す：

```bash
find "<フォルダパス>" -maxdepth 2 -type f \( -iname "*.mp4" -o -iname "*.mov" -o -iname "*.m4v" -o -iname "*.m4a" -o -iname "*.mp3" -o -iname "*.wav" \) 2>/dev/null
```

複数見つかったら、どれを処理するかユーザーに確認する。

---

## STEP 2：無音カットを実行する

同梱スクリプトを **システムの `python3`** で実行する（追加の仮想環境は不要）。`<skill>` はこのスキルのあるディレクトリ（base directory基準）：

```bash
python3 <skill>/scripts/cut_silence.py "<ファイルの絶対パス>"
```

パラメータを調整したい場合（例：短い間もカット／屋外で環境音あり）：

```bash
python3 <skill>/scripts/cut_silence.py "<ファイルパス>" --noise -35 --min 0.2
```

スクリプトが `【STEP 1/3】〜【STEP 3/3】` の進捗と、元の長さ・カット量・出力先を表示する。

---

## STEP 3：結果を報告する

完了後、以下をユーザーに伝える：

- 元の長さ → カット後の長さ
- カットした秒数・短縮率
- 出力ファイル名（`元の名前_cut.mp4` ／ 音声は `_cut.m4a`）
- 次のステップの提案（テロップ入れ・エディタでの仕上げなど）

## パラメータ調整ガイド

| 状況 | 推奨設定 |
|---|---|
| 屋外・環境音あり | `--noise -25` |
| 静かな室内収録（標準） | `--noise -30`（デフォルト） |
| 短い間もカットしたい | `--min 0.2` |
| 間を少し残したい | `--min 0.5` |
| より自然なカット | `--pad 0.12` |

## よくあるエラーと対処

| エラー | 原因 | 対処 |
|---|---|---|
| `command not found: ffmpeg` | ffmpeg 未導入 | STEP 0 で `brew install ffmpeg` |
| `カットできる無音区間が見つかりませんでした` | 無音がほとんど無い／閾値が厳しい | `--noise -25` など値を大きくして再実行 |
| `h264_videotoolbox` 関連エラー | Intel Mac等で非対応 | このスキルは Apple Silicon Mac 専用 |
| 音声ファイルなのに映像を探そうとする | — | 音声は自動判定され `_cut.m4a` で出力される（正常） |

## 注意事項

- カット箇所は自然なつなぎになるよう、前後に約 0.08 秒のパディングを残す。
- 環境音や BGM がある動画は `--noise` の調整が必要な場合がある。
- 出力は元ファイルと同じフォルダに `_cut` を付けて保存される（元ファイルは残る）。
