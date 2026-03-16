@echo off
echo Building Horde Survivor for browser...

pip install pygbag

echo Preparing main.py with UTF-8 encoding fix...
python -c "
import shutil
shutil.copy('spill.py', 'main.py')
# Read as bytes, write with utf-8 encoding declaration
with open('main.py', 'rb') as f:
    content = f.read()
# Add encoding declaration if not present
if b'# -*- coding' not in content[:100]:
    content = b'# -*- coding: utf-8 -*-\n' + content
with open('main.py', 'wb') as f:
    f.write(content)
print('main.py ready')
"

echo Running pygbag build...
pygbag --build main.py

echo Copying to server...
if not exist horde_server\static\game mkdir horde_server\static\game
xcopy /E /Y build\web\* horde_server\static\game\

echo.
echo Done! Now restart app.py and open /game in your browser.
pause
