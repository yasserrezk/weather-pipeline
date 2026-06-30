@echo off

cd /d "%~dp0"
docker compose down

echo ==============================
echo Checking dependencies
echo ==============================

python -m pip install -r requirements.txt


echo ==============================
echo Starting Docker PostgreSQL
echo ==============================

docker compose up -d


echo ==============================
echo Waiting for database startup
echo ==============================

timeout /t 30

echo ==============================
echo Done
echo ==============================

pause