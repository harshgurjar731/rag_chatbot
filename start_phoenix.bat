@echo off
cd /d "%~dp0"
call venv\Scripts\activate
echo Starting Phoenix Server...
phoenix serve
