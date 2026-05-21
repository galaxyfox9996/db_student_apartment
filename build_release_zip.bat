@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

call "%~dp0build_exe.bat"
if errorlevel 1 (
    echo.
    echo 打包步骤失败，因此没有生成压缩包。
    pause
    exit /b 1
)

if not exist "dist\StudentApartmentSystemSQLite" (
    echo 未找到 dist\StudentApartmentSystemSQLite，无法创建压缩包。
    pause
    exit /b 1
)

if exist "release\StudentApartmentSystemSQLite.zip" del /f /q "release\StudentApartmentSystemSQLite.zip"
if not exist release mkdir release

powershell -NoProfile -Command "Add-Type -AssemblyName 'System.IO.Compression.FileSystem'; $source = (Resolve-Path 'dist\StudentApartmentSystemSQLite').Path; $target = Join-Path (Resolve-Path 'release').Path 'StudentApartmentSystemSQLite.zip'; if (Test-Path $target) { Remove-Item $target -Force }; [System.IO.Compression.ZipFile]::CreateFromDirectory($source, $target)"
if errorlevel 1 (
    echo 压缩失败，请查看上面的错误信息。
    pause
    exit /b 1
)

echo.
echo 发布压缩包已生成：release\StudentApartmentSystemSQLite.zip
pause
endlocal
