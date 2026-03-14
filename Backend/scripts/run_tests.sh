#!/bin/bash
# ─────────────────────────────────────────────────────────────────────
# Sandbox Test Runner
# Runs tests for Python / JavaScript / Go repos
# Usage: run_tests.sh <language> [timeout_seconds]
# The repo must be mounted at /app
# ─────────────────────────────────────────────────────────────────────

set -euo pipefail

LANG="${1:-python}"
TIMEOUT="${2:-120}"
RESULT_FILE="/app/.test_results.json"

echo '{"status":"running","language":"'"$LANG"'"}' > "$RESULT_FILE"

run_with_timeout() {
    timeout "$TIMEOUT" "$@" || true
}

case "$LANG" in
    python)
        # Install project deps if requirements.txt exists
        if [ -f /app/requirements.txt ]; then
            pip install --no-cache-dir -q -r /app/requirements.txt 2>/dev/null || true
        fi
        if [ -f /app/pyproject.toml ]; then
            pip install --no-cache-dir -q -e /app 2>/dev/null || true
        fi

        # Run pytest with JSON report
        cd /app
        run_with_timeout python -m pytest \
            --tb=short -q --no-header \
            --json-report --json-report-file="$RESULT_FILE" \
            2>/dev/null || true

        # If json-report plugin not available, fallback to text parsing
        if [ ! -s "$RESULT_FILE" ] || ! python -c "import json; json.load(open('$RESULT_FILE'))" 2>/dev/null; then
            PYTEST_OUTPUT=$(run_with_timeout python -m pytest --tb=short -q --no-header 2>&1 || true)
            PASSED=$(echo "$PYTEST_OUTPUT" | grep -oP '\d+ passed' | grep -oP '\d+' || echo "0")
            FAILED=$(echo "$PYTEST_OUTPUT" | grep -oP '\d+ failed' | grep -oP '\d+' || echo "0")
            echo "{\"status\":\"done\",\"passed\":$PASSED,\"failed\":$FAILED,\"output\":\"$(echo "$PYTEST_OUTPUT" | head -20 | sed 's/"/\\"/g')\"}" > "$RESULT_FILE"
        fi
        ;;

    javascript|typescript)
        cd /app
        # Install deps
        if [ -f /app/package.json ]; then
            npm install --ignore-scripts 2>/dev/null || true
        fi

        # Run tests
        TEST_OUTPUT=$(CI=true run_with_timeout npm test -- --ci --watchAll=false 2>&1 || true)
        PASSED=$(echo "$TEST_OUTPUT" | grep -oP 'Tests:\s+\K\d+(?= passed)' || echo "0")
        FAILED=$(echo "$TEST_OUTPUT" | grep -oP 'Tests:\s+\K\d+(?= failed)' || echo "0")
        echo "{\"status\":\"done\",\"passed\":$PASSED,\"failed\":$FAILED,\"output\":\"$(echo "$TEST_OUTPUT" | tail -20 | sed 's/"/\\"/g')\"}" > "$RESULT_FILE"
        ;;

    go)
        cd /app
        TEST_OUTPUT=$(run_with_timeout go test -v -count=1 ./... 2>&1 || true)
        PASSED=$(echo "$TEST_OUTPUT" | grep -c "--- PASS:" || echo "0")
        FAILED=$(echo "$TEST_OUTPUT" | grep -c "--- FAIL:" || echo "0")
        echo "{\"status\":\"done\",\"passed\":$PASSED,\"failed\":$FAILED,\"output\":\"$(echo "$TEST_OUTPUT" | tail -20 | sed 's/"/\\"/g')\"}" > "$RESULT_FILE"
        ;;

    *)
        echo "{\"status\":\"error\",\"message\":\"Unsupported language: $LANG\"}" > "$RESULT_FILE"
        ;;
esac

# Output results to stdout for docker logs
cat "$RESULT_FILE"
