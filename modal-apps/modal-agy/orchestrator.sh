#!/usr/bin/env bash
set -euo pipefail

declare -a TARGETS=(
  ".agents"
  ".qwen"
  ".gemini"
  ".claude"
  ".hermes"
  ".codex"
  ".cursor-plugin"
  ".config/kilocode"
  ".config/opencode"
)

PERSIST_ROOT="/mnt/persistent_agents"

for TARGET in "${TARGETS[@]}"; do
  FULL_PATH="${HOME}/${TARGET}"
  if [ -d "$FULL_PATH" ]; then
    PARENT_DIR=$(dirname "$TARGET")
    BASE_NAME=$(basename "$TARGET")
    DEST_PARENT="${PERSIST_ROOT}/${PARENT_DIR}"
    DEST_DIR="${DEST_PARENT}/${BASE_NAME}"

    mkdir -p "$DEST_PARENT"

    for SUB_ROOM in agents skills commands plugins; do
      ROOM_PATH="${FULL_PATH}/${SUB_ROOM}"
      DEST_ROOM="${DEST_DIR}/${SUB_ROOM}"

      if [ -d "$ROOM_PATH" ] && [ ! -L "$ROOM_PATH" ]; then
        mkdir -p "$DEST_ROOM"
        cp -a "${ROOM_PATH}/." "$DEST_ROOM/"
        rm -rf "$ROOM_PATH"
        ln -sfn "$DEST_ROOM" "$ROOM_PATH"
      else
        mkdir -p "$DEST_ROOM"
        ln -sfn "$DEST_ROOM" "$ROOM_PATH"
      fi
    done
  fi
done

npm install -g @anthropic/claude-code
npm install -g gemini-cli
