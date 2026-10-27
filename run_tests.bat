@echo off
set PYTHON_PATH="C:\Users\hp\AppData\Local\Programs\Python\Python312\python.exe"
if exist %PYTHON_PATH% (
    %PYTHON_PATH% -m unittest discover -s tests -v
) else (
    python -m unittest discover -s tests -v
)
pause

