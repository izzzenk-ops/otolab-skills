# ストーリー画像の作り方（承認後にだけ実行する）

## 前提を確認する

1. **承認済みの文面**（STEP 7でOKが出ていること）
2. `参考_デザイン/<発信者名>/デザインプロファイル.md`
3. `写真素材/` の写真

足りないものがあれば、何が必要かを伝えて止まる。**推測で作らない。**

## 手順

1. `references/common/design_kijun.md` とデザインプロファイルを読む
2. 1枚につき1つのHTMLを作る（`作成済み/<日付_テーマ>/html/01.html` …）
3. レンダリング
   ```bash
   python3 <このスキルのディレクトリ>/scripts/render_stories.py <html/フォルダ> <png/フォルダ>
   ```
4. **1枚目をReadで開いて目視確認**（文字はみ出し・写真の欠け・コントラスト）
5. 崩れていたらHTMLを直して再レンダリング

## HTMLテンプレート（1080×1920）

デザインプロファイルのCSS変数を差し込んで使う。文字の載せ方は2パターンだけ。

```html
<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><style>
  :root{
    --bg:#F7F3EE; --text:#3A3330; --accent:#E4785F;
    --font:"Hiragino Maru Gothic ProN","ヒラギノ丸ゴ ProN W4","Hiragino Sans",sans-serif;
    --band:rgba(255,255,255,.92);   /* 白帯 */
    --overlay:rgba(255,255,255,.72); /* 全面オーバーレイ（黒なら rgba(0,0,0,.45) と --text:#fff */
  }
  *{margin:0;padding:0;box-sizing:border-box}
  html,body{width:1080px;height:1920px;overflow:hidden}
  body{font-family:var(--font);background:var(--bg);position:relative}
  .photo{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
  .overlay{position:absolute;inset:0;background:var(--overlay)}
  /* 上下2割を必ず空ける */
  .stage{position:absolute;left:0;right:0;top:20%;bottom:20%;
         display:flex;flex-direction:column;justify-content:center;
         gap:34px;padding:0 96px}
  .block{background:var(--band);border-radius:10px;padding:22px 28px;
         font-size:44px;line-height:1.55;color:var(--text);text-align:center}
  .plain{font-size:44px;line-height:1.6;color:var(--text);text-align:center} /* オーバーレイ時 */
  .em{color:var(--accent);font-weight:700}      /* 1枚に1箇所まで */
  .lead{font-size:58px;font-weight:700}          /* 見出し1行。1枚に1つまで */
</style></head><body>
  <img class="photo" src="../../../写真素材/xxx.jpg">
  <!-- 全面オーバーレイのときだけ <div class="overlay"></div> -->
  <div class="stage">
    <div class="block">1ブロック目のテキスト</div>
    <div class="block">2ブロック目<br>文節で改行する</div>
  </div>
</body></html>
```

## 品質の基準

- **上下2割に文字がかかっていない**
- 1ブロックは1〜2行。文節で改行
- 強調（`.em` / `.lead`）は**1枚に1箇所まで**
- 色は3つまで／フォントは1種
- 写真の上に直接白文字を置かない（帯かオーバーレイで浮かせる）
- ブロック数は文字量の選択に従う（多め6〜9／標準3〜5／少なめ1〜2）

## 焼き込めないもの

アンケート・質問箱・リンクスタンプはインスタのアプリ機能なので画像にできない。
**「この枚に◯◯スタンプを置く」という指示として文面.mdに残す**（消さない）。
