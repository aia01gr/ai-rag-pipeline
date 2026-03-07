@echo off
REM ============================================================
REM  Build rag_client.exe with PyInstaller
REM  Run from the folder that contains rag_client.py
REM ============================================================

echo.
echo === RAG Client - Build .exe ===
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Installing via winget...
    echo.
    winget install Python.Python.3.12 --source winget --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo.
        echo Auto-install failed.
        echo Download Python manually from: https://python.org
        echo IMPORTANT: Check "Add Python to PATH" during install
        echo Then run this bat again.
        echo.
        pause
        exit /b 1
    )
    echo.
    echo Python installed. Close and reopen this window, then run this bat again.
    pause
    exit /b 0
)

echo Python found:
python --version
echo.

REM Install dependencies
echo [1/3] Installing dependencies...
python -m pip install httpx pyinstaller --quiet --upgrade
if errorlevel 1 (
    echo ERROR: pip install failed
    pause
    exit /b 1
)
echo   OK
echo.

REM Build exe
echo [2/3] Compiling rag_client.exe...
echo   (This takes 1-2 minutes...)
echo.
python -m PyInstaller ^
    --onefile ^
    --name rag_client ^
    --console ^
    --hidden-import httpx ^
    --hidden-import httpx._transports.default ^
    --hidden-import anyio ^
    --hidden-import anyio._backends._asyncio ^
    --clean ^
    rag_client.py

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller failed
    pause
    exit /b 1
)

REM Create install folder
echo.
echo [3/3] Creating RAGClient\ folder...
if not exist "RAGClient" mkdir RAGClient
copy /Y dist\rag_client.exe RAGClient\
if exist "config.json" (
    copy /Y config.json RAGClient\
) else (
    echo   config.json not found - using defaults
)

echo.
echo ============================================================
echo  Build complete!
echo ============================================================
echo.
echo Files in RAGClient\:
dir /b RAGClient\
echo.
echo Next steps:
echo  1. Copy RAGClient\ folder where you want (e.g. C:\RAGClient\)
echo.
echo  2. Update claude_desktop_config.json:
echo     {
echo       "mcpServers": {
echo         "rag-pipeline": {
echo           "command": "C:\\RAGClient\\rag_client.exe"
echo         }
echo       }
echo     }
echo.
echo  3. Restart Claude Desktop
echo.
pause
