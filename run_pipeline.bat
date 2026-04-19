@echo off
REM Agent Plutus — Daily Pipeline Launcher
REM Scheduled via Windows Task Scheduler for weekdays at 4:00 PM PT

set PYTHON=python
set SCRIPT_DIR=%~dp0
set PIPELINE_SCRIPT=%SCRIPT_DIR%src\daily_pipeline.py

echo [%date% %time%] Starting Agent Plutus...

"%PYTHON%" "%PIPELINE_SCRIPT%" %*

set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% EQU 0 (
    echo [%date% %time%] Pipeline completed successfully.
) else if %EXIT_CODE% EQU 2 (
    echo [%date% %time%] Pipeline completed with warnings.
) else (
    echo [%date% %time%] Pipeline failed with exit code %EXIT_CODE%.
)

exit /b %EXIT_CODE%
