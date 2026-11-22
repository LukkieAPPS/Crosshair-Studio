@echo off
setlocal
cd /d "%~dp0"
py -3.12 -m pip install --upgrade pip
py -3.12 -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto failed
py -3.12 -m PyInstaller --noconfirm --clean --windowed --name CrosshairStudio --collect-all pynput --collect-all PySide6 --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 main.py
if errorlevel 1 goto failed
echo.
echo Build complete: dist\CrosshairStudio\CrosshairStudio.exe
pause
exit /b 0
:failed
echo.
echo Build failed. Check the error above.
pause
exit /b 1
