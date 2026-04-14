# 設置編碼為 UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " 專案強力清理腳本 (PowerShell 版)" -ForegroundColor Cyan
Write-Host " 保留: 單機版/, client/ 核心程式碼" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$root = "c:\Tolerance_Project"

# 1. 定義要刪除的檔案路徑 (相對於根目錄)
$filesToDelete = @(
    "project_structure.txt",
    "server\ai_app_recovered.py",
    "server\ai_app_recovered_utf8.py",
    "fix_csv_encoding.py",
    "read_excel.py",
    "convert_machines.py",
    "test_api.py",
    "server\test_contact_retrieval.py",
    "sys_exec.txt",
    "server\sys_exec.txt",
    "server\package.json",
    "server\package-lock.json",
    "package-lock.json",
    "CLOUD_COMPARISON.md",
    "DEPLOYMENT_CHECKLIST.md",
    "QUICK_START.md",
    "README_CLOUD.md",
    "SETUP_IMPROVEMENTS.md",
    "TROUBLESHOOTING.md",
    "Smart_Engineering_Flow.txt",
    "server\README.md",
    "server\data\graph.svg",
    "server\data\records (3).json",
    "server\data\ISO_286_2_test2.xlsx",
    "build_win.bat",
    "setup.bat",
    "setup.sh",
    "cleanup.bat",
    "PURGE_PROJECT.bat",
    "server\data\ontology_export.csv",
    "server\data\edge_map.pkl",
    "data\machines.csv"
)

# 2. 定義要刪除的目錄路徑
$dirsToDelete = @(
    ".hypothesis",
    ".ruff_cache",
    ".pytest_cache",
    "server\__pycache__",
    "tests\__pycache__",
    "server\scripts\__pycache__",
    "server\recommendation\__pycache__",
    "server\validation\__pycache__",
    "logs",
    "docs",
    "ppt",
    "others",
    "electron",
    "data",
    "server\scripts\diagnostics",
    "tests",
    "openspec",
    ".kiro",
    ".claude",
    ".agent"
)

Write-Host "`n[1/2] 正在刪除檔案..." -ForegroundColor Yellow
foreach ($f in $filesToDelete) {
    $path = Join-Path $root $f
    if (Test-Path $path) {
        Remove-Item -Path $path -Force -ErrorAction SilentlyContinue
        Write-Host "  已刪除: $f"
    }
}

Write-Host "`n[2/2] 正在刪除目錄..." -ForegroundColor Yellow
foreach ($d in $dirsToDelete) {
    $path = Join-Path $root $d
    if (Test-Path $path) {
        Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  已移除目錄: $d"
    }
}

Write-Host "`n==========================================" -ForegroundColor Green
Write-Host " 清理完成！你的專案現在非常精簡。" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green

# 提示使用者按任意鍵退出
Read-Host "`n按 Enter 鍵結束"

# 自刪
$MyInvocation.MyCommand.Path | Remove-Item -Force -ErrorAction SilentlyContinue
