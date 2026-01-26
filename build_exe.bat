@echo off
echo === Creazione EXE Cerca Voli ===
echo.

echo 1. Installazione PyInstaller...
pip install pyinstaller

echo.
echo 2. Creazione EXE...
pyinstaller --onefile --windowed --name "CercaVoli" ^
    --add-data "skyscanner;skyscanner" ^
    --hidden-import=typeguard ^
    --collect-all typeguard ^
    cerca_voli_gui.py
    
echo.
echo === FATTO! ===
echo L'eseguibile si trova in: dist\CercaVoli.exe
pause