@echo off
echo Uygulama Gelistirici Modunda Baslatiliyor...

:: Backend bagimliliklarini kontrol et
echo Backend kutuphaneleri kontrol ediliyor...
pip install -r "%~dp0backend\requirements.txt"

:: Güncel backend kodlarını resources klasörüne kopyala (Eğer build alınırsa güncel olsun diye)
copy /Y "%~dp0backend\pdm_logic.py" "%~dp0frontend\resources\pdm_logic.py"
copy /Y "%~dp0backend\server.py" "%~dp0frontend\resources\server.py"
copy /Y "%~dp0backend\config.json" "%~dp0frontend\resources\config.json"

cd /d "%~dp0frontend"
npm start
