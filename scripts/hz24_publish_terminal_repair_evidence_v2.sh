#!/usr/bin/env bash

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "${SCRIPT_DIR}/lib/project_paths.sh"
PROJECT_DIR="$(aideal_project_dir)"

cd "${PROJECT_DIR}" || false
python3 scripts/ops/publish_terminal_repair_evidence.py
