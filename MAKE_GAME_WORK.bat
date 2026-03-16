@echo off
echo =============================================
echo   HORDE SURVIVOR - Browser Game Setup
echo =============================================
echo.
echo This script must be run from the "Rouge lite" folder
echo (the folder that contains spill.py and final_server)
echo.

REM Check we are in the right folder
if not exist spill.py (
    echo ERROR: Cannot find spill.py in this folder!
    echo Please move this .bat file to the same folder as spill.py
    echo and run it again.
    pause
    exit /b 1
)

if not exist final_server\app.py (
    echo ERROR: Cannot find final_server\app.py
    echo Please move this .bat file to the same folder as spill.py
    echo and run it again.
    pause
    exit /b 1
)

echo Found spill.py - good!
echo Found final_server\app.py - good!
echo.

REM Step 1: Create main.py with UTF-8 fix
echo [Step 1/3] Creating main.py...
python -c "
with open('spill.py', 'rb') as f:
    content = f.read()
if b'coding' not in content[:100]:
    content = b'# -*- coding: utf-8 -*-\n' + content
with open('main.py', 'wb') as f:
    f.write(content)
print('  main.py created OK')
"
if errorlevel 1 (
    echo ERROR: Python failed. Is Python installed?
    pause
    exit /b 1
)

REM Step 2: Build with pygbag
echo.
echo [Step 2/3] Building browser version (this takes 1-2 minutes)...
echo   Please wait - a browser window may open, just ignore it.
echo.
pygbag --build main.py
echo.

REM Step 3: Find and copy the output
echo [Step 3/3] Copying game files to server...

REM pygbag can output to different places depending on version
set FOUND=0

if exist build\web\index.html (
    echo   Found output at: build\web\
    set FOUND=1
    if not exist final_server\static\game mkdir final_server\static\game
    xcopy /E /Y /I /Q build\web\* final_server\static\game\
    goto :done
)

if exist main\build\web\index.html (
    echo   Found output at: main\build\web\
    set FOUND=1
    if not exist final_server\static\game mkdir final_server\static\game
    xcopy /E /Y /I /Q main\build\web\* final_server\static\game\
    goto :done
)

REM Search harder
for /r . %%f in (index.html) do (
    echo %%f | findstr /i "web" >nul
    if not errorlevel 1 (
        echo   Found output at: %%~dpf
        set FOUND=1
        if not exist final_server\static\game mkdir final_server\static\game
        xcopy /E /Y /I /Q "%%~dpf*" final_server\static\game\
        goto :done
    )
)

:done
if %FOUND%==0 (
    echo.
    echo ERROR: Could not find pygbag output!
    echo   The build may have failed. Check the output above for errors.
    echo   Common fix: make sure pygbag is installed: pip install pygbag
    pause
    exit /b 1
)

echo.
echo =============================================
echo   SUCCESS!
echo =============================================
echo.
echo Game files are now in: final_server\static\game\
echo.
echo TO FINISH:
echo   1. Stop app.py if it is running (Ctrl+C)
echo   2. Run app.py again:  python final_server\app.py
echo   3. Open your browser to:  http://localhost:5000/game
echo.
pause
