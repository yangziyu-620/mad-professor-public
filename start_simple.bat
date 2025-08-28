@echo off
chcp 65001 >nul
echo 正在启动AI Professor...

:: 激活conda环境
call conda activate mad-professor

:: 启动程序
python main.py

pause 