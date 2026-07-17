# bunseki-my-account 環境セットアップ（Windows用・ベータ）
#
# 目的: Windowsの受講生のPCでも、このスクリプト1本で実行環境
#       （Python / ffmpeg / yt-dlp / faster-whisper venv）を揃える。
# 使い方（PowerShell）: powershell -ExecutionPolicy Bypass -File setup.ps1
# 設計:
#   - 冪等。既に入っているものはスキップ、無いものだけ入れる。毎回流してよい。
#   - winget（Windows標準のパッケージ管理）を使う。無い場合は導入を促す。
#   - ※Windows版はベータ（実機未検証）。うまくいかない項目は最後にまとめて表示する。

$ErrorActionPreference = "Continue"
function Ok($m)   { Write-Host "  [OK] $m" -ForegroundColor Green }
function Info($m) { Write-Host "  ->  $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "  [!] $m" -ForegroundColor Yellow }
function Step($m) { Write-Host "`n$m" -ForegroundColor White }
$Fail = 0

Step "0/4 マシン確認"
if (-not $IsWindows -and $env:OS -ne "Windows_NT") {
  Warn "このスクリプトはWindows用です。Macは setup.sh を使ってください。"; exit 1
}
Ok "Windows"

# ---- winget ---------------------------------------------------------------
Step "1/4 winget（パッケージ管理）"
$winget = Get-Command winget -ErrorAction SilentlyContinue
if (-not $winget) {
  Warn "winget が見つかりません。Microsoft Storeで「アプリ インストーラー」を更新してから再実行してください。"
  $Fail = 1
} else { Ok "winget あり" }

# ---- Python / ffmpeg / yt-dlp --------------------------------------------
Step "2/4 Python・ffmpeg・yt-dlp"
function Ensure-Winget($id, $cmd, $label) {
  if (Get-Command $cmd -ErrorAction SilentlyContinue) { Ok "$label 導入済み"; return }
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { Warn "$label を入れられません（winget無し）"; return 1 }
  Info "$label をインストール中…"
  winget install --id $id -e --accept-source-agreements --accept-package-agreements -h *> $null
  if (Get-Command $cmd -ErrorAction SilentlyContinue) { Ok "$label を入れました" }
  else { Warn "$label のインストールに失敗（PowerShellを開き直すとPATHが通ることがあります）"; return 1 }
}
if (Ensure-Winget "Python.Python.3.12" "python" "Python") { $Fail = 1 }
if (Ensure-Winget "Gyan.FFmpeg"        "ffmpeg" "ffmpeg") { $Fail = 1 }
if (Ensure-Winget "yt-dlp.yt-dlp"      "yt-dlp" "yt-dlp") { $Fail = 1 }

# ---- faster-whisper venv --------------------------------------------------
Step "3/4 文字起こし環境（faster-whisper venv）"
$venv = Join-Path $HOME "telop-tool\venv"
$vpy  = Join-Path $venv "Scripts\python.exe"
$pyOK = $false
if (Test-Path $vpy) {
  & $vpy -c "import faster_whisper" 2>$null
  if ($LASTEXITCODE -eq 0) { $pyOK = $true }
}
if ($pyOK) { Ok "faster-whisper 導入済み ($venv)" }
else {
  $py = (Get-Command python -ErrorAction SilentlyContinue)
  if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue) }
  if (-not $py) { Warn "python が見つからずvenvを作れません"; $Fail = 1 }
  else {
    Info "venv を作成し faster-whisper をインストール中（初回は数分かかります）…"
    New-Item -ItemType Directory -Force -Path (Split-Path $venv) *> $null
    & $py.Source -m venv $venv
    & $vpy -m pip install --quiet --upgrade pip faster-whisper *> $null
    & $vpy -c "import faster_whisper" 2>$null
    if ($LASTEXITCODE -eq 0) { Ok "faster-whisper を入れました ($venv)" }
    else { Warn "faster-whisper のインストールに失敗しました"; $Fail = 1 }
  }
}

# ---- 最終確認 -------------------------------------------------------------
Step "4/4 最終チェック"
if (Get-Command yt-dlp -ErrorAction SilentlyContinue) { Ok "yt-dlp あり" } else { Warn "yt-dlp なし"; $Fail = 1 }
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) { Ok "ffmpeg あり" } else { Warn "ffmpeg なし"; $Fail = 1 }
if ((Test-Path $vpy) -and (& $vpy -c "import faster_whisper" 2>$null; $LASTEXITCODE -eq 0)) { Ok "faster-whisper あり" } else { Warn "faster-whisper なし"; $Fail = 1 }

Write-Host ""
if ($Fail -eq 0) {
  Write-Host "OK セットアップ完了。分析を開始できます。" -ForegroundColor Green
  exit 0
} else {
  Write-Host "一部が未完了です。上の [!] の項目を確認してください（PowerShellを開き直すと直ることがあります）。" -ForegroundColor Yellow
  exit 1
}
