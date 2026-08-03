@echo off
setlocal
cd /d "%~dp0"
python -B scripts\problem_solving_quality_next_loop_web.py --open-browser chrome
endlocal
