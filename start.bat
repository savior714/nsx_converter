@echo off
chcp 65001 > nul
echo.
echo ======================================
echo   NSX to Markdown Converter (Web GUI)
echo ======================================
echo.
echo Python check...
where python >nul 2>nul || where py >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Python not found!
    echo.
    echo Download Python: https://www.python.org/downloads/
    echo Install Python 3.7 or higher.
    echo.
    pause
    exit /b 1
)
echo Python found! Starting program...
echo.
py nsx_web_gui.py
if errorlevel 1 (
    python nsx_web_gui.py
)
pause

