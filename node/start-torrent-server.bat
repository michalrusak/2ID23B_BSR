@echo off
echo Starting Torrent Server...
echo.
echo This will start the torrent API server on port 3000
echo Make sure Python backend is running on port 5001
echo.

cd /d %~dp0

:: Check if node_modules exists
if not exist "node_modules\" (
    echo Installing dependencies...
    call npm install
    echo.
)

:: Start the torrent server
echo Starting torrent server on port 3000...
node src/torrent-server.js

pause
