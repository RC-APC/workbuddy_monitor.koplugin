@echo off
REM ============================================================
REM  WorkBuddy -> KOReader bridge, background launcher
REM  - starts with pythonw (no window at all)
REM  - to stop: Task Manager -> end pythonw.exe
REM  - searches: WorkBuddy managed python first, then PATH
REM ============================================================
cd /d "%~dp0"

IF NOT EXIST "wb-bridge.py" (
    echo ERROR: wb-bridge.py not found. Put this bat in the same folder.
    pause
    exit /b 1
)

REM --- 1) WorkBuddy managed pythons (deterministic, no PATH needed) ---
set "PYW="
for /d %%V in ("%USERPROFILE%\.workbuddy\binaries\python\versions\*") do (
    if not defined PYW if exist "%%V\pythonw.exe" set "PYW=%%V\pythonw.exe"
)
if not defined PYW if exist "%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\pythonw.exe" (
    set "PYW=%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\pythonw.exe"
)

REM --- 2) fall back to PATH scan, skipping Store stubs ---
if not defined PYW for /f "delims=" %%P in ('where python 2^>nul') do (
    if not defined PYW if exist "%%~dP%%~pPpythonw.exe" set "PYW=%%~dP%%~pPpythonw.exe"
)

if defined PYW (
    start "" "%PYW%" wb-bridge.py
    echo Bridge started in background: %PYW%
    goto :verify
)

echo ERROR: no usable python found.
echo Searched: %USERPROFILE%\.workbuddy\binaries\python\ and PATH.
pause
exit /b 1

:verify
timeout /t 2 >nul 2>nul
where curl >nul 2>nul
IF NOT %ERRORLEVEL%==0 (
    echo Skip health check: curl not available. Test manually in browser:
    echo   http://127.0.0.1:8765/health
    goto :end
)
curl -s --max-time 3 http://127.0.0.1:8765/health >"%TEMP%\wb_health.txt" 2>nul
findstr /c:"ok" "%TEMP%\wb_health.txt" >nul 2>nul
IF %ERRORLEVEL%==0 (
    echo VERIFY OK: bridge is answering on port 8765.
) ELSE (
    echo WARN: health check failed. Bridge may need a few seconds; test:
    echo   http://127.0.0.1:8765/health
)
:end
echo.
echo Kindle side: use this PC's LAN IP, e.g. http://192.168.137.1:8765
pause
