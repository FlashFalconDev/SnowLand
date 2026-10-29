@echo off
setlocal
cd /d "%~dp0..\snowland-frontend"
call npm run dev -- --host 127.0.0.1 --port 3000 --strictPort
