@echo off
REM Agent Plutus — Daily Pipeline Launcher
REM Scheduled via Windows Task Scheduler for weekdays at 4:00 PM PT

set PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
set SCRIPT_DIR=%~dp0
set PIPELINE_SCRIPT=%SCRIPT_DIR%daily_pipeline.py

REM Inject ANTHROPIC_API_KEY from project-local file (process-scoped only).
REM File should contain a single line with the key only and is gitignored.
REM Process-scoped `set` keeps the key out of the parent shell so it does not
REM interfere with Claude Code's OAuth subscription billing.
if exist "%SCRIPT_DIR%.anthropic_key" (
    for /f "usebackq delims=" %%K in ("%SCRIPT_DIR%.anthropic_key") do set "ANTHROPIC_API_KEY=%%K"
    echo [%date% %time%] Loaded ANTHROPIC_API_KEY from %SCRIPT_DIR%.anthropic_key
) else (
    echo [%date% %time%] WARNING: %SCRIPT_DIR%.anthropic_key not found; narrator will use findings-only fallback.
)

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
