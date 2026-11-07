@echo off
REM Gera o executável do Windows em dist\PT2VHF-SDR-Tool\
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pytest -q || exit /b 1
pyinstaller --noconfirm pt2vhf.spec
echo.
echo Pronto: dist\PT2VHF-SDR-Tool\PT2VHF-SDR-Tool.exe
