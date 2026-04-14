$source = "c:\Tolerance_Project\新增資料夾\軸承座\軸承座-3.STP"
$destFolder = "c:\Tolerance_Project\test_3d_viz\models"
$destFile = "$destFolder\bearing_housing.stp"

if (!(Test-Path $destFolder)) {
    New-Item -ItemType Directory -Path $destFolder -Force
}

if (Test-Path $source) {
    Copy-Item -Path $source -Destination $destFile -Force
    Write-Host "✅ Model copied successfully to $destFile"
} else {
    Write-Error "❌ Source file not found: $source"
}
