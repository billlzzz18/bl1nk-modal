#!/bin/bash
# Modal AGY Sandbox - Tools only, plugins pulled at runtime
#
# Usage:
#   ./run.sh                              # setup tools in sandbox
#   ./run.sh shell                        # interactive shell
#   ./run.sh work <project-url>           # clone project
#   ./run.sh <any command>                # run command directly

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE_PY="$SCRIPT_DIR/image.py"
STATE_FILE="$SCRIPT_DIR/.sandbox_state"

# Hardcoded MCP server URLs (verified working)
MCP_CONTEXT7="https://github.com/upstash/context7"

# Load state if exists
if [ -f "$STATE_FILE" ]; then
    source "$STATE_FILE"
fi

if [ $# -eq 0 ]; then
    # No arguments - setup tools in sandbox
    exec modal shell "$IMAGE_PY::run_cmd" --pty --cmd \
        "cd /tmp && git --version && gh --version && cargo --version && rustc --version && python3 --version && agy plugin install $MCP_CONTEXT7 && agy plugin list && echo '=== Ready ===' && bash"
elif [ "$1" = "shell" ]; then
    shift
    exec modal shell "$IMAGE_PY::run_cmd" --pty --cmd "cd /tmp && bash"
elif [ "$1" = "work" ] && [ -n "$2" ]; then
    PROJECT_URL="$2"
    PROJECT_NAME=$(basename "$PROJECT_URL" .git)
    cat > "$STATE_FILE" << EOF
SANDBOX_PROJECT_URL="$PROJECT_URL"
SANDBOX_PROJECT_NAME="$PROJECT_NAME"
EOF
    exec modal shell "$IMAGE_PY::run_cmd" --pty --cmd \
        "cd /tmp && git clone $PROJECT_URL /tmp/$PROJECT_NAME && cd /tmp/$PROJECT_NAME && bash"
else
    CMD="$*"
    exec modal run "$IMAGE_PY::run_cmd" --cmd "cd /tmp && $CMD"
fi
