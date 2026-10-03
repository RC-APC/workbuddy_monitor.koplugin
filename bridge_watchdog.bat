@echo off
REM WorkBuddy -> KOReader bridge watchdog.
REM If port 8765 is not listening, start the bridge with pythonw (no window).
REM Called by Task Scheduler every few minutes and at logon, so the bridge
REM self-heals after crashes / reboots. No literal non-ASCII in this file:
REM the python path uses %USERPROFILE% (expanded natively by cmd), and the
REM script lives on D: (ASCII). Keep it that way.
set PORT=8765
set PY=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe
set SCRIPT=D:\kual_deliver\workbuddy-koreader-monitor\wb-bridge.py
netstat -an | findstr :%PORT% | findstr LISTEN >nul
if %errorlevel%==0 goto :done
echo %date% %time% bridge down, restarting >> "%~dp0bridge_watchdog.log"
start "" "%PY%" "%SCRIPT%"
:done
