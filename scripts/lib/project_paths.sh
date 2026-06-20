#!/usr/bin/env bash
# Resolve the repository root from one authoritative implementation.

aideal_project_dir() {
  if [ -n "${AIDEAL_PROJECT_DIR:-}" ]; then
    printf '%s\n' "${AIDEAL_PROJECT_DIR}"
    return 0
  fi

  local helper_dir
  helper_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  CDPATH= cd -- "${helper_dir}/../.." && pwd
}
