@echo off
setlocal
cd /d C:\FlashFalconDev\SnowLand\snowland
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("C:\FlashFalconDev\SnowLand\.env.local") do set "%%A=%%B"
set "Mysql_NAME=%SNOWLAND_TEST_DB_NAME%"
set "Mysql_USER=%SNOWLAND_TEST_DB_USER%"
set "Mysql_PASSWORD=%SNOWLAND_TEST_DB_PASSWORD%"
set "Mysql_HOST=%SNOWLAND_TEST_DB_HOST%"
set "Mysql_PORT=%SNOWLAND_TEST_DB_PORT%"
set "SNOWLAND_LOCAL_AUTH_BYPASS=1"
.venv\Scripts\python.exe manage.py migrate --noinput
if errorlevel 1 pause & exit /b 1
.venv\Scripts\python.exe manage.py seed_minimal_local
if errorlevel 1 pause & exit /b 1
.venv\Scripts\python.exe manage.py seed_console_demo
if errorlevel 1 pause & exit /b 1
.venv\Scripts\python.exe manage.py process_snowland_jobs
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8999
