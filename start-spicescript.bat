@echo off
rem Starts the SpiceScript backend and frontend in two separate windows, then opens the app.
rem Keep both windows open while you use the app. Close them to stop the servers.
start "SpiceScript backend" cmd /k "cd /d C:\Users\falak\Downloads\spicescript-v6\spicescript\backend && C:\Users\falak\AppData\Local\Programs\Python\Python315\python.exe -m uvicorn app.main:app --reload"
start "SpiceScript frontend" cmd /k "cd /d C:\Users\falak\Downloads\spicescript-v6\spicescript\frontend && npm run dev"
echo Starting both servers. The app opens in about 10 seconds.
timeout /t 10 /nobreak >nul
start http://localhost:5173
