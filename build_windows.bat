@echo off
REM Gera instalador e portátil do Windows em dist\
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt || exit /b 1
set QT_QPA_PLATFORM=offscreen
python -m pytest -q || exit /b 1
python packaging\make_version_info.py || exit /b 1
pyinstaller --noconfirm pt2vhf.spec || exit /b 1
dist\PT2VHF-SDR-Tool\PT2VHF-SDR-Tool.exe --selftest || exit /b 1
for /f %%v in ('python packaging\make_version_info.py') do set VER=%%v
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /DAppVersion=%VER% packaging\installer.iss || exit /b 1
copy /Y dist\PT2VHF-SDR-Tool-portable.exe dist\PT2VHF-SDR-Tool-%VER%-win-x64-portable.exe
echo Pronto: dist\PT2VHF-SDR-Tool-%VER%-win-x64-setup.exe e -portable.exe
