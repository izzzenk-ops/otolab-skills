#!/usr/bin/env python3
"""report.html の相対パス画像をbase64で埋め込み、1ファイルで完結するHTMLを作る。

  <venv-python> inline_images.py <report.html> [--out report_1file.html] [--width 200]

なぜ必要か:
  報告書は frames/ の画像を相対パスで参照している。フォルダごと持ち出さないと
  画像が表示されず、チャットに1枚だけ送る・受講生に渡す・別PCで開くと壊れる。
  埋め込んでおけば html 1枚をどこへ送っても完全に再現できる。

- 画像は表示幅に合わせて縮小してから埋め込む（Pillowがあれば。無ければ原寸のまま）
- 元ファイルは書き換えず、別名（既定: 同フォルダの report_1file.html）で出力する
"""
import base64
import mimetypes
import re
import sys
from pathlib import Path


def shrink(data, width):
    """Pillowがあれば幅widthに縮小して返す。無ければ原データをそのまま返す。"""
    try:
        import io

        from PIL import Image
        im = Image.open(io.BytesIO(data))
        if im.width <= width:
            return data
        h = round(im.height * width / im.width)
        im = im.convert("RGB").resize((width, h), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=72, optimize=True)
        return buf.getvalue()
    except Exception:
        return data


def main():
    args = sys.argv[1:]
    src = Path(args[0]).resolve()
    out = Path(args[args.index("--out") + 1]) if "--out" in args \
        else src.with_name(src.stem + "_1file.html")
    width = int(args[args.index("--width") + 1]) if "--width" in args else 200

    html = src.read_text(encoding="utf-8")
    base = src.parent
    embedded, missing, total = 0, [], 0

    def repl(m):
        nonlocal embedded, total
        attr, path = m.group(1), m.group(2)
        if path.startswith(("data:", "http://", "https://")):
            return m.group(0)
        f = (base / path).resolve()
        if not f.exists():
            missing.append(path)
            return m.group(0)
        data = shrink(f.read_bytes(), width)
        mime = mimetypes.guess_type(f.name)[0] or "image/jpeg"
        b64 = base64.b64encode(data).decode()
        embedded += 1
        total += len(b64)
        return f'{attr}="data:{mime};base64,{b64}"'

    html = re.sub(r'(src|href)="([^"]+\.(?:jpg|jpeg|png|gif|webp|svg))"',
                  repl, html, flags=re.I)
    out.write_text(html, encoding="utf-8")

    print(f"埋め込み: {embedded}枚 / 出力: {out} "
          f"({out.stat().st_size/1024/1024:.1f}MB)")
    if missing:
        print(f"⚠ 見つからなかった画像 {len(missing)}件: {missing[:5]}")


if __name__ == "__main__":
    main()
