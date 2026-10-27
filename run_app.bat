@echo off
set PYTHON_PATH="C:\Users\hp\AppData\Local\Programs\Python\Python312\python.exe"
if exist %PYTHON_PATH% (
    %PYTHON_PATH% -m streamlit run app.py
) else (
    streamlit run app.py
)
pause

