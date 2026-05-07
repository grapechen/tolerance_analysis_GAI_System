# ============================================================
#  setup_mysql_win.ps1
#  在 Windows 上自動下載、安裝 MySQL Community Server 8.x
#  並建立 tolerance_db 資料庫
#  執行方式: 以「系統管理員」身份在 PowerShell 執行
#  PS> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#  PS> .\setup_mysql_win.ps1
# ============================================================

$ErrorActionPreference = "Stop"
$MYSQL_ROOT_PASS = "Bb88710307"
$DB_NAME         = "tolerance_db"
$MYSQL_PORT      = 3306
$INSTALL_DIR     = "C:\mysql8"
$DOWNLOAD_URL    = "https://dev.mysql.com/get/Downloads/MySQL-8.0/mysql-8.0.37-winx64.zip"
$ZIP_PATH        = "$env:TEMP\mysql8.zip"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " MySQL 8 + ISO 286 DB Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ── Step 1: 檢查是否已安裝 MySQL ──────────────────────────────────────────
Write-Host "`n[1/5] Checking existing MySQL..." -ForegroundColor Yellow

$mysqlSvc = Get-Service -Name "MySQL80" -ErrorAction SilentlyContinue
if ($mysqlSvc) {
    Write-Host "  MySQL80 service already exists — skipping install." -ForegroundColor Green
    if ($mysqlSvc.Status -ne "Running") {
        Start-Service -Name "MySQL80"
        Start-Sleep -Seconds 3
    }
} else {
    # ── Step 2: 下載 MySQL ZIP ────────────────────────────────────────────
    Write-Host "`n[2/5] Downloading MySQL 8.0 ZIP (~300 MB)..." -ForegroundColor Yellow
    if (-not (Test-Path $ZIP_PATH)) {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $DOWNLOAD_URL -OutFile $ZIP_PATH -UseBasicParsing
        Write-Host "  Download complete." -ForegroundColor Green
    } else {
        Write-Host "  ZIP already exists, skipping download." -ForegroundColor Green
    }

    # ── Step 3: 解壓縮 ────────────────────────────────────────────────────
    Write-Host "`n[3/5] Extracting to $INSTALL_DIR..." -ForegroundColor Yellow
    if (Test-Path $INSTALL_DIR) { Remove-Item $INSTALL_DIR -Recurse -Force }
    Expand-Archive -Path $ZIP_PATH -DestinationPath "C:\" -Force
    # Rename versioned folder to mysql8
    $extracted = Get-ChildItem "C:\" -Directory | Where-Object { $_.Name -like "mysql-8*" } | Select-Object -First 1
    if ($extracted) { Rename-Item $extracted.FullName $INSTALL_DIR }
    Write-Host "  Extracted to $INSTALL_DIR" -ForegroundColor Green

    # ── Step 4: 初始化 & 安裝服務 ─────────────────────────────────────────
    Write-Host "`n[4/5] Initializing MySQL data directory..." -ForegroundColor Yellow
    $DATA_DIR = "$INSTALL_DIR\data"
    $BIN      = "$INSTALL_DIR\bin"

    # Write my.ini
    @"
[mysqld]
basedir=$INSTALL_DIR
datadir=$DATA_DIR
port=$MYSQL_PORT
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
default-authentication-plugin=mysql_native_password

[client]
port=$MYSQL_PORT
"@ | Set-Content "$INSTALL_DIR\my.ini" -Encoding ASCII

    # Initialize (creates root with empty password)
    & "$BIN\mysqld.exe" --defaults-file="$INSTALL_DIR\my.ini" --initialize-insecure --console
    Start-Sleep -Seconds 5

    # Install as Windows service
    & "$BIN\mysqld.exe" --install MySQL80 --defaults-file="$INSTALL_DIR\my.ini"
    Start-Service -Name "MySQL80"
    Start-Sleep -Seconds 5
    Write-Host "  MySQL service started." -ForegroundColor Green

    # Set root password
    & "$BIN\mysql.exe" -u root --connect-expired-password -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '$MYSQL_ROOT_PASS'; FLUSH PRIVILEGES;"
    Write-Host "  Root password set." -ForegroundColor Green

    # Add to PATH for this session
    $env:Path += ";$BIN"
}

# ── Step 5: 建立資料庫 ────────────────────────────────────────────────────
Write-Host "`n[5/5] Creating database '$DB_NAME'..." -ForegroundColor Yellow

# Find mysql.exe
$mysqlExe = Get-Command mysql -ErrorAction SilentlyContinue
if (-not $mysqlExe) {
    if (Test-Path "$INSTALL_DIR\bin\mysql.exe") {
        $mysqlExe = "$INSTALL_DIR\bin\mysql.exe"
    } else {
        # Try Program Files
        $candidates = @(
            "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
            "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe"
        )
        foreach ($c in $candidates) { if (Test-Path $c) { $mysqlExe = $c; break } }
    }
}

if (-not $mysqlExe) {
    Write-Host "  ERROR: mysql.exe not found. Please add MySQL bin dir to PATH." -ForegroundColor Red
    exit 1
}

$createDB = @"
CREATE DATABASE IF NOT EXISTS ``$DB_NAME``
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
"@
& $mysqlExe -u root -p"$MYSQL_ROOT_PASS" -e $createDB
Write-Host "  Database '$DB_NAME' ready." -ForegroundColor Green

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " MySQL ready!  Now run:" -ForegroundColor Cyan
Write-Host "   cd C:\Tolerance_Project\server" -ForegroundColor White
Write-Host "   python populate_iso286.py" -ForegroundColor White
Write-Host "========================================`n" -ForegroundColor Cyan
