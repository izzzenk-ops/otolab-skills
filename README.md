# otolab-skills（おとラボのスキル集）

オトラボ受講生向けにClaude Codeスキルを配布するための、Claude Codeプラグイン・マーケットプレイス。

**現在の状態：ローカル準備＋初回コミット済み。GitHubへの公開（`gh repo create` / `git push`）はまだ行っていません（親セッションが招待コード削除を検証してから公開する）。**

## 構造

```
otolab-skills/                              ← マーケットプレイスのルート（将来このままGitHubリポジトリのルートにする）
├── .claude-plugin/
│   └── marketplace.json                    ← マーケットプレイス定義（プラグイン一覧）
├── plugins/
│   └── otolab-insta/                       ← プラグイン本体
│       ├── .claude-plugin/
│       │   └── plugin.json                 ← プラグイン定義
│       └── skills/
│           ├── bunseki-reel/               ← リール1本徹底分析
│           ├── bunseki-competitor-account/ ← 競合アカウント分析
│           ├── bunseki-my-account/         ← 自分のアカウント分析
│           ├── insta-concept-design/       ← アカウントコンセプト設計
│           ├── daihon-copy-make/           ← 参考台本から台本作成
│           └── daihon-kyaba-vlog/          ← ギャップ1日Vlog台本作成
└── README.md（このファイル）
```

この構造は `~/.claude/plugins/marketplaces/claude-plugins-official/` の実物（Anthropic公式マーケットプレイス）を参考に、以下のスキーマに合わせて作成した：

- マーケットプレイスのルート直下に `.claude-plugin/marketplace.json` を置く（`name` / `description` / `owner` / `plugins[]` を持つ）
- 各プラグインは `plugins/<プラグイン名>/.claude-plugin/plugin.json` を持つ（`name` / `version` / `description` / `author`）
- プラグイン内の `skills/` ディレクトリはデフォルトで自動認識される（`plugin.json` 側で明示指定は不要。1階層下に `<スキル名>/SKILL.md` を置く標準構成）

## 受講生向け：導入手順（2コマンド）

リポジトリを **public** で公開する前提。Claude Codeで以下の2行を順に実行するだけ。

```
/plugin marketplace add izzzenk-ops/otolab-skills
/plugin install otolab-insta@otolab-skills
```

1行目でマーケットプレイス（このリポジトリ）をClaude Codeに登録し、2行目で `otolab-insta` プラグイン（6スキル一式）をインストールする。インストール後は `~/.claude/skills/` に自作したときと同じ感覚で、6つのスキルがそのまま使えるようになる。

> ※ `bunseki-my-account` は以前 単独リポジトリ `izzzenk-ops/bunseki-my-account` でも配布していたが、このスキル集に統合済み。今後はこのスキル集（`otolab-insta`）経由でのインストールを推奨。

### 更新が受講生に届く仕組み

けんじさんがGitHubリポジトリ側でスキルを更新してpushしても、**受講生の環境には自動では反映されない**。受講生が `/plugin marketplace update` を実行してマーケットプレイス定義を最新化し、必要なら `/plugin install otolab-insta@otolab-skills` を再実行（または `/plugin update otolab-insta` 相当の更新コマンド）することで初めて更新が届く。そのため、スキルを更新したタイミングでDiscord等で「アップデートしたので `/plugin marketplace update` してください」と受講生に案内する運用が必要になる。

## けんじさん向け：新スキル追加・更新時の手順

**新しいスキルを追加するとき：**
1. `~/.claude/skills/<新スキル名>/` を、このリポジトリの `plugins/otolab-insta/skills/<新スキル名>/` にコピー（rsyncで `__pycache__` 等の不要ファイルを除外）
2. コピーした中の個人情報・特定ブランド名・個人絶対パスを一般化（下記「一般化のルール」参照）
3. `plugins/otolab-insta/.claude-plugin/plugin.json` の `version` をセマンティックバージョニングで上げる（新機能追加なら `1.x.0`、バグ修正なら `1.0.x`）
4. `plugins/otolab-insta/.claude-plugin/plugin.json` の `description` にスキル名を追記
5. `.claude-plugin/marketplace.json` の該当プラグインの `description` も同様に更新
6. ローカルで動作確認してからコミット・push（公開手順は下記）

**既存スキルを更新するとき：**
1. `~/.claude/skills/<スキル名>/` の変更点を、このリポジトリの対応フォルダに同様の手順でコピー・一般化
2. `plugin.json` の `version` を上げる
3. コミット・push

**一般化のルール（今回の作業で適用した基準）：**
- 個人名「けんじさん」「けんじ個人」→「運営者」「運営者個人」に置き換える
- 特定ブランド名（おとばな／OTOGIBANASHI／desse／いい感じケンジ 等）の**例示**は削除・一般化する
- ただし「メモリの個人アカウント名を報告書に書かない」等の**ガード・ロジックの意味は絶対に壊さない**。固有名詞だけ抜いて一般化する（例：「メモリにあるけんじ個人や他人のアカウント名（おとばな／desse等）を書かない」→「メモリにある運営者個人や他人のアカウント名を書かない」）
- `~/Documents/Claude/Projects/発信プロフィール/profile.md` を参照する仕組みはそのまま残す（受講生にも同じ場所にプロフィールを置いてもらえば個別化が効く設計のため）
- 判断に迷うものは変更せず、作業ログ・レポートに「要判断」として残す

## 公開するとき（このセッションでは実行しない・手順のみ）

ローカルの `git init` → `git add -A` → `git commit`（初回コミット）までは実施済み。**`gh repo create` と `git push` はこのセッションでは絶対に実行しない**（親セッションが招待コード削除を検証してから公開する）。以下は親セッション／けんじさんが公開時に実行するコマンド。

```bash
cd ~/Documents/Claude/Projects/otolab-skills

# GitHub上にリポジトリを作成（受講生配布のため public）
gh repo create izzzenk-ops/otolab-skills --public --source=. --remote=origin

# push
git push -u origin main
```

公開後、受講生には上記「導入手順（2コマンド）」を案内する。

## 個人情報の一般化について

コピーした6スキル内の、けんじさん個人・特定ブランドの例示（「おとばな」「OTOGIBANASHI SUPPLY」「desse」「いい感じケンジ」「けんじさん」「華月／@kiiiiiii0228」等）は一般的な表現・プレースホルダに置き換え済み。招待コード等の秘匿情報も削除済み。詳細はタスク完了時のレポートを参照。
