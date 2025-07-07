@echo off
chcp 65001 >nul
title AI Professor - Mad Professor启动器

echo.
echo ==========================================
echo    AI Professor - Mad Professor 启动器
echo ==========================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到Python，请确保Python已正确安装并添加到环境变量中
    echo.
    pause
    exit /b 1
)

echo [信息] 检测到Python环境...

:: 激活conda环境
echo [信息] 正在激活conda环境: mad-professor
call conda activate mad-professor
if %errorlevel% neq 0 (
    echo [警告] 无法激活conda环境 mad-professor，尝试使用系统环境
    echo [提示] 请确保已安装conda并创建了名为 mad-professor 的环境
) else (
    echo [信息] conda环境 mad-professor 已激活
)

:: 检查主程序文件是否存在
if not exist "main.py" (
    echo [错误] 未找到main.py文件，请确保在正确的目录中运行此脚本
    echo.
    pause
    exit /b 1
)

:: 检查依赖是否安装
echo [信息] 检查依赖项...
python -c "import PyQt6" >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] 检测到缺少依赖项，正在安装...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [错误] 依赖项安装失败，请手动运行: pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
)

echo [信息] 正在启动AI Professor...
echo.

:: 启动应用程序
python main.py

:: 如果程序异常退出，显示错误信息
if %errorlevel% neq 0 (
    echo.
    echo [错误] 程序异常退出，错误代码: %errorlevel%
    echo.
    pause
) else (
    echo.
    echo [信息] 程序正常退出
) 