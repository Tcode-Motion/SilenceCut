@echo off
title SilenceCut
cd /d "%~dp0"
if not "%~1"=="" goto cli
py silencecut_web.py
if %errorlevel% equ 0 exit /b 0
python silencecut_web.py
if %errorlevel% equ 0 exit /b 0
echo.
echo  SilenceCut could not start. Python 3 and ffmpeg are needed.
pause
exit /b 1
:cli
py silencecut.py %*
if %errorlevel% equ 0 goto done
python silencecut.py %*
:done
pause
