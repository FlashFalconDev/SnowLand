@echo off
setlocal
cd /d "%~dp0..\snowland"
if not exist "%~dp0..\.env.local" (
  echo Missing local database settings. Run tools\snowland-test-db.ps1 -Action setup first.
  exit /b 1
)
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%~dp0..\.env.local") do set "%%A=%%B"
if not "%SNOWLAND_TEST_DB_NAME%"=="test_snowland" exit /b 1
if not "%SNOWLAND_TEST_DB_HOST%"=="127.0.0.1" exit /b 1
if not "%SNOWLAND_TEST_DB_PORT%"=="3308" exit /b 1
set "Mysql_NAME=%SNOWLAND_TEST_DB_NAME%"
set "Mysql_USER=%SNOWLAND_TEST_DB_USER%"
set "Mysql_PASSWORD=%SNOWLAND_TEST_DB_PASSWORD%"
set "Mysql_HOST=%SNOWLAND_TEST_DB_HOST%"
set "Mysql_PORT=%SNOWLAND_TEST_DB_PORT%"
set "SNOWLAND_LOCAL_AUTH_BYPASS=1"
rem Starting the server never migrates, seeds or runs scheduled jobs automatically.
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8999
