#!/bin/bash
# bunseki-competitor-account 環境セットアップ（ブートストラップ）
#
# 目的: 何も入っていない受講生のMacでも、このスクリプト1本で
#       運営者と同じ実行環境（Homebrew / yt-dlp / ffmpeg / mlx_whisper venv）を揃える。
# 使い方: bash setup.sh
# 設計:
#   - 冪等。既に入っているものは skip、無いものだけ入れる。毎回STEP0で流してよい。
#   - Homebrew も自動インストール対象。sudoが要る場面は受講生が自分のMacのパスワードを打つ（想定内）。
#   - 対応: Apple Silicon (arm64) Mac のみ。
set -u

ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; }
info() { printf "  \033[34m→\033[0m %s\n" "$1"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$1"; }
step() { printf "\n\033[1m%s\033[0m\n" "$1"; }

FAIL=0

step "0/4 マシン確認"
if [ "$(uname -s)" != "Darwin" ]; then
  warn "macOS 専用スキルです（このMacは $(uname -s)）。中止します。"; exit 1
fi
if [ "$(uname -m)" != "arm64" ]; then
  warn "Apple Silicon (M系) 専用です。mlx_whisperがこのCPUでは動きません。中止します。"; exit 1
fi
ok "Apple Silicon Mac"

# ---- Homebrew --------------------------------------------------------------
step "1/4 Homebrew"
BREW=""
for cand in /opt/homebrew/bin/brew "$(command -v brew 2>/dev/null)"; do
  [ -n "$cand" ] && [ -x "$cand" ] && BREW="$cand" && break
done
if [ -z "$BREW" ]; then
  info "未インストール。公式インストーラで入れます（Macのパスワードを聞かれたら入力してください）…"
  NONINTERACTIVE=1 /bin/bash -c \
    "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" \
    && ok "Homebrew を入れました" \
    || { warn "Homebrew の自動インストールに失敗。手動で https://brew.sh を実行して再試行してください"; FAIL=1; }
  [ -x /opt/homebrew/bin/brew ] && BREW=/opt/homebrew/bin/brew
else
  ok "導入済み ($BREW)"
fi
# このスクリプト内のPATHにbrewを通す
[ -n "$BREW" ] && eval "$("$BREW" shellenv)" 2>/dev/null

# ---- yt-dlp / ffmpeg -------------------------------------------------------
step "2/4 yt-dlp・ffmpeg"
if [ -n "$BREW" ]; then
  for pkg in yt-dlp ffmpeg; do
    if command -v "$pkg" >/dev/null 2>&1; then
      ok "$pkg 導入済み"
    else
      info "$pkg をインストール中…"
      "$BREW" install "$pkg" >/dev/null 2>&1 && ok "$pkg を入れました" \
        || { warn "$pkg のインストールに失敗（brew install $pkg を手動で試してください）"; FAIL=1; }
    fi
  done
else
  warn "Homebrewが無いため yt-dlp/ffmpeg を入れられません"; FAIL=1
fi

# ---- mlx_whisper venv ------------------------------------------------------
step "3/4 文字起こし環境（mlx_whisper venv）"
VENV="$HOME/telop-tool/venv"
VPY="$VENV/bin/python3"
if [ -x "$VPY" ] && "$VPY" -c "import mlx_whisper" >/dev/null 2>&1; then
  ok "mlx_whisper 導入済み ($VENV)"
  # プロフィール切り出しで使う pillow を既存venvにも補う
  if ! "$VPY" -c "import PIL" >/dev/null 2>&1; then
    info "pillow を追加中…"; "$VPY" -m pip install --quiet pillow >/dev/null 2>&1 && ok "pillow を入れました"
  fi
else
  info "venv を作成し mlx-whisper をインストール中（初回は数分かかります）…"
  PY3="$(command -v python3 || true)"
  if [ -z "$PY3" ] && [ -n "$BREW" ]; then
    "$BREW" install python >/dev/null 2>&1; PY3="$(command -v python3 || true)"
  fi
  if [ -z "$PY3" ]; then
    warn "python3 が見つからずvenvを作れません"; FAIL=1
  else
    mkdir -p "$HOME/telop-tool"
    "$PY3" -m venv "$VENV" \
      && "$VPY" -m pip install --quiet --upgrade pip mlx-whisper pillow \
      && "$VPY" -c "import mlx_whisper" >/dev/null 2>&1 \
      && ok "mlx_whisper を入れました ($VENV)" \
      || { warn "mlx-whisper のインストールに失敗しました"; FAIL=1; }
  fi
fi

# ---- 最終確認 --------------------------------------------------------------
step "4/4 最終チェック"
command -v yt-dlp  >/dev/null 2>&1 && ok "yt-dlp  $(yt-dlp --version 2>/dev/null)"  || { warn "yt-dlp なし";  FAIL=1; }
command -v ffmpeg  >/dev/null 2>&1 && ok "ffmpeg  あり"                              || { warn "ffmpeg なし";  FAIL=1; }
[ -x "$VPY" ] && "$VPY" -c "import mlx_whisper" >/dev/null 2>&1 && ok "mlx_whisper あり" || { warn "mlx_whisper なし"; FAIL=1; }

echo
if [ "$FAIL" -eq 0 ]; then
  printf "\033[1;32m✅ セットアップ完了。分析を開始できます。\033[0m\n"
  exit 0
else
  printf "\033[1;33m⚠ 一部が未完了です。上の ! の項目を確認してください。\033[0m\n"
  exit 1
fi
