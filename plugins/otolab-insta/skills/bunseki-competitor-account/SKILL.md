---
name: bunseki-competitor-account
description: "【競合アカウント分析】Instagramの競合・参考アカウントを徹底分析してHTMLビジュアル報告書を作るスキル。アカウントURLを受け取り、Claude in Chromeでプロフィール・リール一覧・再生数を収集し、伸びている上位リール＋最新リールをyt-dlpで実ダウンロード→mlx_whisperで全文文字起こしして、サムネイル設計の法則・台本の共通構成・伸びている理由・自分のアカウントへの活かし方を、サムネ画像入りの1枚のHTML報告書にまとめてChromeで開く。「競合アカウント分析して」「競合分析して」「このアカウントを徹底分析して」「参考アカウントを分析して報告書にして」「このアカウントのリールを文字起こしして分析して」「アカウント研究して」「このアカウントなんで伸びてるのか調べて」「bunseki-competitor-account」などのフレーズで必ず起動すること。運用中に新しい競合・参考アカウントを見つけて深く研究したい場合は常にこのスキルを使うこと。※Discordに軽量テキストレポートを送るだけの分析は instagram-analysis、自分のアカウントのコンセプト設計は insta-concept-design を使う。"
---

# 競合アカウント分析（bunseki-competitor-account）｜参考アカウント徹底分析→ビジュアル報告書

## このスキルについて

参考アカウントのURLを受け取り、**実データ（サムネ画像・再生数・文字起こし全文）に基づいて**分析し、1枚のHTML報告書としてChromeで開く。日々の運用中に「このアカウント良さそう」と見つけたとき、分析にかかる時間を数時間→自動に短縮するためのスキル。

**使い分け（重要）:**
- このスキル → 徹底分析＋ビジュアル報告書（ローカルHTML）。運用中のアカウント研究用
- `instagram-analysis` → 閲覧ベースの軽量レポートをDiscordに送信。立ち上げ初期用
- `insta-concept-design` → 自分のアカウントのコンセプト設計そのもの

分析結果を台本づくりに使う場合は、報告書完成後に daihon-copy-make（または発信者固定の台本スキル）等の該当スキルへ引き継ぐ。

## 前提条件

このスキルは**受講生に配って同じ状態で使える自己セットアップ型**（[[feedback-skills-student-distributable]]）。真の前提はこれだけ：

- **Apple Silicon（M系）Mac**（mlx_whisperの制約）
- Chrome拡張（Claude in Chrome）が接続済みで、Chromeで instagram.com にログイン済み
- Claude Code が使えること

`yt-dlp`・`ffmpeg`・`mlx_whisper`（＋必要ならHomebrew本体）は**入っていなくてよい**。STEP 0の `setup.sh` が自動で入れる。何も入っていない受講生のMacでも初回実行で環境が整う。

その他：
- 所要時間の目安: **10〜20分**（DL＋文字起こし15本・並行パイプライン使用時。初回のみ環境構築で+数分）。開始時にユーザーへ目安を伝え、各STEPの節目で短く経過報告すること
- 急ぎのときは**クイックモード**：「クイックで」「急ぎで」と言われたら対象を**上位5本＋最新3本**に減らす（`--top 5 --latest 3`）。約5〜10分で完了し、報告書にクイック分析である旨を明記する

## 出力先

```
~/Documents/Claude/Projects/競合アカウント分析/<username>_<YYYYMMDD>/
├── data/        reels.json, selection.json, stats.json, profile.json
├── thumbs/      選定外リールのカバー画像（NNN_ID.jpg…）
├── reels/       動画mp4＋カバー画像jpg＋download_log.json
│   └── transcripts/   ID.txt（全文）, ID.segments.json
└── report.html  最終報告書（画像は相対パス参照なのでフォルダごと移動可）
```

## デフォルトの分析対象

**伸びている上位10本＋最新5本**（重複は除く、ピン留めは「最新」から除外）。ユーザーが本数を指定したらそれに従う。全リール分析を頼まれたら「数時間＋数GBかかる」ことを伝えてから実行する。

---

## STEP 0：環境セットアップ＋ツール読み込み

**最初に必ず環境セットアップを実行する**（受講生の何も入っていないMacでも、これで yt-dlp・ffmpeg・mlx_whisper・必要ならHomebrew まで自動で揃う）。冪等なので毎回流してよい：

```bash
bash <skill>/scripts/setup.sh
```

- 全項目が ✓ で「✅ セットアップ完了」なら次へ。初回はHomebrew/whisperの導入で数分かかることがある（受講生のMacで、パスワードを聞かれたら本人が入力する）
- `!` が残る（一部失敗）場合は、その項目をユーザーに伝える。ネットワークや権限が原因のことが多く、再実行で解決することが多い

次に、Chromeツールが遅延読み込みの場合、**1回のToolSearch**でまとめてロードする：

```
select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__javascript_tool
```

- `tabs_context_mcp`でタブ確認。拡張未接続なら「Chrome拡張を接続してから再度試してください」と伝えて終了
- 出力先ディレクトリを作成し、このスキルのscripts/があるパス（base directory基準）を控えておく

## STEP 1：プロフィール収集

1. `navigate`でプロフィールURLへ移動し、スクリーンショットで状態確認
   - 未ログイン → 「Chromeでinstagram.comにログインしてから再度試してください」と伝えて終了
   - プライベートアカウント → フォローしていないと見られないため伝えて終了
2. `get_page_text`で収集し `data/profile.json` に保存：表示名・@ユーザー名・フォロワー数・投稿数・bio全文・ハイライト名・外部リンク
3. スクリーンショットでフィード全体の色味・世界観・統一感をメモ（サムネ法則分析の材料）
4. **プロフィールのスクショを `data/profile.png` に保存**（報告書ヘッダーの右側に載せる）。Chrome拡張のscreenshotはファイル保存できないため、次のヘルパーを使う：

```bash
bash <skill>/scripts/capture_chrome_window.sh <scratchpad>/chrome_profile.png
```

その後PILでブラウザUI（上部タブ・アドレスバー・ブックマークバー、左サイドバー）を除いたIGコンテンツ領域（プロフィール＋グリッド1段目まで）を切り出して `data/profile.png` に保存する。切り出し座標はスクショをReadして目視で決める（Retinaは2倍px）。撮影に失敗したら（別Spaceのフルスクリーン等）スクショなしで続行し、報告書のhead-shotブロックを削除する

## STEP 2：リール一覧の収集と選定

`https://www.instagram.com/<username>/reels/` に移動。**知っておくべき制約が3つ**：

1. navigate直後はグリッド未描画で`a[href*="/reel/"]`が0件になる。**2〜3秒待ってから**収集を始める（0件でも構造を疑う前にまず待って再実行）
2. グリッドの再生数テキストは「カウントアイコンを見る29.7万」のようにアクセシビリティラベル付き。ラベルを除去して数字だけ抽出する
3. **署名付きCDN URL（サムネのimg.src）はツール結果に含めるとBLOCKEDされ、クリップボード書き込みも権限拒否される**。よってサムネURLは収集せず、パス・再生数・ピン留めだけをJSONで直接返す。サムネ画像はSTEP 3でyt-dlpが取る

Instagramのグリッドは仮想化されていてスクロールすると古い要素がDOMから消えるため、`javascript_tool`でwindow上のアキュムレータに溜めながらスクロールする：

```js
window.__ig = window.__ig || {};
document.querySelectorAll('main a[href*="/reel/"]').forEach(a => {
  const pinned = !!a.querySelector('svg[aria-label*="固定"], svg[aria-label*="Pinned"]');
  const key = a.href.split('?')[0];
  const m = (a.textContent || '').replace(/カウントアイコンを見る/g, '').trim().match(/^[\d.,]+(万|億|千)?/);
  if (!window.__ig[key]) window.__ig[key] = {thumb: null, views: m ? m[0] : '', pinned};
});
window.scrollBy(0, window.innerHeight * 3);
Object.keys(window.__ig).length
```

- 返り値（件数）が2回連続で増えなくなるまで繰り返す（1〜2秒間隔）。100本を大きく超えるアカウントは直近100本程度で打ち切ってよい（その旨を報告書に書く）
- 最後に `JSON.stringify(Object.fromEntries(Object.entries(window.__ig).map(([u,v]) => [new URL(u).pathname, v])))` で取り出す（パスのみなので安全に返せる）。結果が長くて途切れたら`.slice(N)`で残りを分割取得し、`data/reels.json` に `{"<フルURL>": {"thumb": null, "views": "...", "pinned": false}}` 形式で保存
- 再生数が取れない（非表示）場合も止まらない：グリッド順で最新15本を選び、報告書に「再生数非表示のため推定」と明記

選定と統計はスクリプトで：

```bash
python3 <skill>/scripts/select_reels.py data/reels.json data/ --top 10 --latest 5
```

`selection.json`（選定結果）と `stats.json`（中央値=平常値・平均・最高・バズ本数）ができる。ここで一度ユーザーに「◯本収集、平常値◯万再生、これから◯本をDL＆文字起こし」と経過報告する。

## STEP 3＋4：ダウンロード＆文字起こし（並行パイプライン）

**DLと文字起こしは1本のパイプラインで並行実行する**（逐次実行に比べ所要時間がほぼ半分になる）。バックグラウンドで起動：

```bash
# 動画DL＋文字起こしを同時進行（run_in_backgroundで起動）
~/telop-tool/venv/bin/python3 <skill>/scripts/pipeline.py data/selection.json reels/ --language ja

# 選定外リールのカバー画像だけ取得（俯瞰ギャラリー用。--excludeで重複DLを回避。パイプラインと並行してよい）
python3 <skill>/scripts/download_thumbs.py data/reels.json thumbs/ --limit 60 --exclude data/selection.json
```

- **パイプライン実行中に、STEP 1-2の情報からプロフィール分析・サムネ法則・数字分析を先に書き進めておく**こと。こうすると完了時に残るのは台本分析と報告書組み立てだけになり、体感が大きく縮む
- yt-dlpはcookieなし→失敗時のみ `--cookies-from-browser chrome` で自動再試行。公開リールは通常cookieなしで落ちる
- 一部失敗しても続行。失敗分は報告書に「◯本はDL不可（閲覧情報のみで分析）」と正直に書く
- 済みファイルはスキップされるので再実行しても安全（個別にやり直す場合は download_reels.py / transcribe.py も使える）
- Whisperの注意: 固有名詞の誤変換はあり得る（明らかなものは文脈で補正、創作はしない）。**末尾の同一文字繰り返し（「短短短短…」等の幻覚）は無視し報告書に含めない**

## STEP 5：分析

実データだけを根拠にする。見ていないものを「〜のはず」と書かない。以下の5つの柱で抽出する：

**A. コンセプト設計** — bioから Who（誰に）× What（何を）× How（どう独自に）を1文に要約。肩書きの数字・実績の見せ方、bio1行目のフック、CTA、ハイライトの役割分担

**B. サムネイル設計の法則** — thumbs/ と reels/ のカバー画像を見比べて抽出：文字数の目安・フォント・縁取り・配置／基調色と統一ルール／人物の表情・構図／コピーの型（数字型・ベネフィット型・違和感型など、実例を引用）

**C. 台本の共通構成** — transcripts/ の全文から：冒頭フックの型（segments.jsonの0〜3秒を全文引用）／展開のブロック構造／オチ・締めの型／口調・語尾・頻出フレーズ／尺と文字数の目安。daihon-eiga-vlogを作ったときのように「この人の型」をテンプレート化する。**あわせて「視聴者心理の設計」**（[[reference-viewer-psychology-blueprint]]）＝各パートが視聴者に起こす効果（どこで疑問/伏線を植え、どこで回収するか、感情の弧）を**効果ベースで**書く。**制作者の内心は断定せず、視聴者側の反応の推定として明示**する（「良いフック」で止めず、なぜ効くか＝移植可能なメカニズムまで）

**D. 伸びの構造** — stats.jsonの平常値（中央値）を基準に、各リールが何倍かを計算。バズ回のテーマ・サムネ・フックの共通点。最新5本とバズ回の違い（運用の変化）

**E. 活かし方** — 明日から真似できる具体アクション4〜6個。**サムネ／フック／台本構成（展開ブロックの組み方・オチの型）／企画選定／数値の見方の5観点をひと通りカバーする**こと。特に台本構成はCで抽出した「この人の型」をユーザーの台本づくりにどう移植するかまで具体化する（ここが抜けやすい）。**丸パクリではなく構造の移植**を勧めること。
- **個別化の材料は発信プロフィールだけを使う**（メモリを勝手にあさらない）：`~/Documents/Claude/Projects/発信プロフィール/profile.md` があれば読んで、その発信（誰に／何を／目的）に合わせて具体化する。無ければ「一般的なインスタ運用者」向けの汎用で書く。⚠️ メモリにある運営者個人や他人のアカウント名を勝手に報告書へ書かない（受講生配布で他人の情報が混ざるため）。※プロフィールMDの新規作成は bunseki-reel が担当（このスキルは読むだけ）

分析が終わったら、台本生成用の **`style_profile.md`** を出力フォルダ直下に保存する（**daihon-copy-makeスキルがこれを読んでユーザーの台本を作る**ための引き継ぎファイル）。含める内容：一言コンセプト／フックの型（実例つき・変形パターンも）／展開のブロック構造／オチの型／**視聴者心理の設計（心理レバー・効果ベース＝どこで何を感じさせ、伏線をどこで回収し、どんな感情の弧か。推定と明示）**／文体ルール（人称・語尾・頻出フレーズ・迂回表現）／尺と文字数／参考にすべき文字起こしファイル名2〜3本／移植時の注意（固有ギャグの丸写し禁止）。報告書セクション5と同じ内容だが、機械可読なプレーンMarkdownで書く。書き方の見本は `~/Documents/Claude/Projects/競合アカウント分析/kanako_vlog_20260710/style_profile.md`

## STEP 6：HTML報告書の生成

1. `<skill>/assets/report_template.html` を読み、**CSSと構造はそのまま**に中身を実データで埋めて `report.html` として保存する（テンプレートの`[[...]]`を置換し、リールカード等は必要数複製）
   - **文字起こし済みのリールカードには必ず`tr-box`ブロック（「文字起こしを見る」開閉＋コピー＋.txt保存ボタン）を付ける**。全文をHTMLエスケープして`<pre class="tr-text">`に埋め込む（ユーザーがワンクリックで台本スキルに渡せるのがこの報告書の価値）。テンプレート末尾の`<script>`（trToggle/trCopy/trDownload）も忘れず含める
   - カード数が多い場合、この埋め込みはEditの繰り返しよりPythonスクリプトでtranscripts/*.txtを読んで一括注入する方が確実
2. 画像は相対パス（`thumbs/000_xxx.jpg`, `reels/<ID>.jpg`）で参照。サムネギャラリーは選定リール分が `reels/<ID>.jpg`、選定外が `thumbs/NNN_<ID>.jpg` に分かれているのでグリッド順（selection.jsonのgrid_index順）に混ぜて並べる。DLに失敗したリールのカードは画像なし（枠のみ）でよい
3. フッターに「確認できなかった項目」を正直に記載（スキップ・推定・打ち切りなど）
4. 完成したらChromeで開く（Chrome拡張のnavigateは`file://`を開けないので必ず`open`コマンドで）：

```bash
open -a "Google Chrome" ~/Documents/Claude/Projects/競合アカウント分析/<dir>/report.html
```

5. 表示検証はヘッドレスChromeでスクリーンショットを撮って画像・レイアウト崩れがないか確認する：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
  --screenshot=<scratchpad>/report_check.png --window-size=1200,2400 --hide-scrollbars \
  "file://<dir>/report.html"
```

## STEP 7：完了報告

- このアカウントの一番のポイントを一言で添えて完了報告
- 報告書のフルパスと、スキップ・推定した項目を伝える
- 「この分析を台本づくりに使うなら **daihon-copy-make** に引き継げる（報告書の🎬ボタンで起動プロンプトをコピーできる）」ことを一言添える

## 注意事項

- ダウンロード間隔（3秒）やスクロール間隔を詰めない。InstagramのレートリミットとアカウントBAN回避のため
- 収集した動画・画像は研究目的のローカル保存。そのまま転載しないようユーザーにも注意を促す（報告書フッターの注意書きで足りる）
- 長時間処理（DL・文字起こし）は run_in_background で走らせ、待ち時間に分析を進める
- 途中で何かが失敗しても**報告書を最後まで届けることを最優先**にする。失敗は隠さず報告書とチャットの両方に書く
