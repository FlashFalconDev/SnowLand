@echo off
setlocal
cd /d C:\FlashFalconDev\SnowLand\snowland-frontend
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("C:\FlashFalconDev\SnowLand\.env.local") do set "%%A=%%B"
npm run dev -- --host 127.0.0.1 --port 5199
