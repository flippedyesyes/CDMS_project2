@echo off
REM Wrapper so that running `coverage ...` uses the current project's virtualenv.
set SCRIPT_DIR=%~dp0
call "%SCRIPT_DIR%\.venv\Scripts\python.exe" -m coverage %*
