<#
.SYNOPSIS
  Tolerance Project — 一次性環境建置腳本（適用於另一台 Windows 電腦）

.DESCRIPTION
  自動化以下步驟：
    1. 找到 conda env tol_env 的 Python（或讓使用者指定）
    2. pip install -r requirements.txt
    3. 驗證 MySQL Server 連線（host=127.0.0.1:3306, user=root, pwd=Bb88710307）
    4. 跑 setup_database.py 建 DB 與 ORM 表
    5. 檢查 ISO 286 Excel 來源檔
    6. 跑 import_all_data.py 匯入 IT/孔/軸公差表

.PARAMETER PythonExe
  指定 Python 執行檔絕對路徑。若未提供，會依序嘗試：
    1. 預設 Anaconda 路徑 C:\Users\<USER>\anaconda3\envs\tol_env\python.exe
    2. PATH 上的 python

.PARAMETER SkipInstall
  跳過 pip install 步驟（只做 DB 建置 + 匯入）

.EXAMPLE
  .\setup.ps1
  .\setup.ps1 -PythonExe "D:\anaconda3\envs\tol_env\python.exe"
  .\setup.ps1 -SkipInstall
#>

param(
    [string]$PythonExe = "",
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$ServerDir   = Join-Path $ProjectRoot "server"
$DbHost      = "127.0.0.1"
$DbPort      = 3306
$DbUser      = "root"
$DbPass      = "Bb88710307"
$DbName      = "tolerance_db"
# 帶 query string 給 ORM/Flask 用；setup_database.py 解析 URL 不夠聰明，要餵不帶 query 的版本
$DbUrl       = "mysql+pymysql://${DbUser}:${DbPass}@${DbHost}:${DbPort}/${DbName}?charset=utf8mb4"
$DbUrlPlain  = "mysql+pymysql://${DbUser}:${DbPass}@${DbHost}:${DbPort}/${DbName}"

function Write-Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "[ERROR] $msg" -ForegroundColor Red }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }

# ── 1. 找 Python ─────────────────────────────────────────────────────────
Write-Step "Locating Python (tol_env)"
if ($PythonExe -eq "") {
    $candidates = @(
        "$env:USERPROFILE\anaconda3\envs\tol_env\python.exe",
        "C:\Users\$env:USERNAME\anaconda3\envs\tol_env\python.exe",
        "C:\Users\User\anaconda3\envs\tol_env\python.exe",
        "C:\ProgramData\anaconda3\envs\tol_env\python.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $PythonExe = $c; break }
    }
}
if ($PythonExe -eq "" -or -not (Test-Path $PythonExe)) {
    Write-Err "找不到 tol_env Python。請用 -PythonExe 指定路徑。"
    Write-Host "  範例：.\setup.ps1 -PythonExe `"D:\anaconda3\envs\tol_env\python.exe`""
    exit 1
}
Write-Ok "Python = $PythonExe"
& $PythonExe --version

# ── 2. pip install requirements ─────────────────────────────────────────
if (-not $SkipInstall) {
    Write-Step "Installing requirements.txt"
    $req = Join-Path $ProjectRoot "requirements.txt"
    if (Test-Path $req) {
        & $PythonExe -m pip install -r $req
        if ($LASTEXITCODE -ne 0) { Write-Err "pip install 失敗"; exit 1 }
        Write-Ok "Dependencies installed"
    } else {
        Write-Warn "找不到 requirements.txt，跳過"
    }
} else {
    Write-Warn "跳過 pip install (--SkipInstall)"
}

# ── 3. 驗證 MySQL 連線 ──────────────────────────────────────────────────
Write-Step "Verifying MySQL connection"
$svc = Get-Service -Name "MySQL*" -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq "Running" } | Select-Object -First 1
if ($null -eq $svc) {
    Write-Err "找不到正在執行的 MySQL 服務。請先安裝 MySQL Server 並設 root 密碼為 $DbPass。"
    Write-Host "  下載：https://dev.mysql.com/downloads/installer/"
    exit 1
}
Write-Ok "MySQL service running: $($svc.Name)"

$pyTest = "import pymysql; c=pymysql.connect(host='$DbHost',port=$DbPort,user='$DbUser',password='$DbPass',connect_timeout=5); print('Server:', c.get_server_info()); c.close()"
& $PythonExe -c $pyTest
if ($LASTEXITCODE -ne 0) {
    Write-Err "pymysql 連不上 MySQL。請確認 root 密碼為 '$DbPass' 且 port $DbPort 開啟。"
    exit 1
}
Write-Ok "MySQL connection OK"

# ── 4. setup_database.py（建 DB + 表） ─────────────────────────────────
Write-Step "Running setup_database.py (create DB + tables)"
$env:DATABASE_URL = $DbUrlPlain  # setup_database.py URL parser 不吃 query string
$env:PYTHONIOENCODING = "utf-8"
Push-Location $ServerDir
try {
    & $PythonExe setup_database.py
    # setup_database.py 在 print 表名時可能因 cp950 編碼炸掉，但表已建好，忽略 exitcode
} finally {
    Pop-Location
}

# 驗證 DB 與表
$verifyTables = "import pymysql; c=pymysql.connect(host='$DbHost',port=$DbPort,user='$DbUser',password='$DbPass',database='$DbName'); cur=c.cursor(); cur.execute('SHOW TABLES'); print('Tables:', sorted(r[0] for r in cur.fetchall())); c.close()"
& $PythonExe -c $verifyTables
if ($LASTEXITCODE -ne 0) { Write-Err "DB / 表驗證失敗"; exit 1 }
Write-Ok "Database & tables ready"

# ── 5. 檢查 ISO 286 Excel ──────────────────────────────────────────────
Write-Step "Checking ISO 286 source files"
$excelDir = Join-Path $ServerDir "data"
$iso1 = Join-Path $excelDir "ISO_286_1_test.xlsx"
$iso2 = Join-Path $excelDir "ISO_286_2_test.xlsx"
$missing = @()
if (-not (Test-Path $iso1)) { $missing += $iso1 }
if (-not (Test-Path $iso2)) { $missing += $iso2 }
if ($missing.Count -gt 0) {
    Write-Err "缺少 ISO 286 Excel 來源檔（已被 .gitignore 排除，需手動複製）："
    $missing | ForEach-Object { Write-Host "  - $_" }
    Write-Host ""
    Write-Host "請從原機 server\data\ 把這兩個檔案複製到上面位置，再重跑此腳本（可用 -SkipInstall 跳過 pip）。"
    exit 1
}
Write-Ok "Excel files present"

# ── 6. 匯入 ISO 286 資料 ───────────────────────────────────────────────
Write-Step "Running import_all_data.py (this can take a few minutes)"
$importScript = Join-Path $ServerDir "scripts\import_all_data.py"
Push-Location $ServerDir
try {
    & $PythonExe $importScript
    if ($LASTEXITCODE -ne 0) { Write-Warn "import_all_data 部分步驟失敗（軸公差需要 ISO_286_2_test2.xlsx，沒有也 OK）" }
} finally {
    Pop-Location
}

# 驗證 IT 表至少有資料
$verifyIT = "import pymysql; c=pymysql.connect(host='$DbHost',port=$DbPort,user='$DbUser',password='$DbPass',database='$DbName'); cur=c.cursor(); cur.execute('SELECT COUNT(*) FROM iso286_tolerance'); n=cur.fetchone()[0]; c.close(); print(f'iso286_tolerance rows: {n}'); exit(0 if n > 0 else 1)"
& $PythonExe -c $verifyIT
if ($LASTEXITCODE -ne 0) { Write-Err "IT 公差表沒有資料，匯入失敗"; exit 1 }
Write-Ok "ISO 286 data imported"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host " Setup 完成！可以執行 run_ai.bat 啟動服務 (port 7011)" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
