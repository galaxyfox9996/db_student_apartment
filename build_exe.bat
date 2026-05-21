@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo 未找到 .venv\Scripts\python.exe，请先创建并安装虚拟环境。
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo 未检测到 PyInstaller，正在安装...
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo PyInstaller 安装失败，无法继续打包。
        pause
        exit /b 1
    )
)

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onedir ^
  --windowed ^
  --name StudentApartmentSystemSQLite ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "打包发布说明.md;." ^
  run_sqlite.py
if errorlevel 1 (
    echo.
    echo 打包失败，请查看上面的错误信息。
    pause
    exit /b 1
)

echo.
echo 打包完成，输出目录：dist\StudentApartmentSystemSQLite
endlocal
