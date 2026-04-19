#!/usr/bin/env bash
# Agent Plutus — Daily Pipeline Launcher (Mac/Linux)
# Schedule with: crontab -e
# Add: 0 16 * * 1-5 /path/to/run_pipeline.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIPELINE_SCRIPT="$SCRIPT_DIR/src/daily_pipeline.py"
PYTHON="${PYTHON:-python3}"
TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"

echo "[$TIMESTAMP] Starting Agent Plutus..."

"$PYTHON" "$PIPELINE_SCRIPT" "$@"
EXIT_CODE=$?

TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$TIMESTAMP] Pipeline completed successfully."
elif [ $EXIT_CODE -eq 2 ]; then
    echo "[$TIMESTAMP] Pipeline completed with warnings."
else
    echo "[$TIMESTAMP] Pipeline failed with exit code $EXIT_CODE."
fi

exit $EXIT_CODE
