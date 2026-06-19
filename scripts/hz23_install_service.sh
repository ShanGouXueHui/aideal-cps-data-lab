#!/usr/bin/env bash
# Install HZ23 observer as a system service. No set -e is used.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${AIDEAL_PROJECT_DIR:-$(cd -- "${SCRIPT_DIR}/.." && pwd)}"
SERVICE_CONFIG="${AIDEAL_HZ23_SERVICE_CONFIG:-${PROJECT_DIR}/config/hz23-service.env}"
UNIT_TEMPLATE="${AIDEAL_HZ23_UNIT_TEMPLATE:-${PROJECT_DIR}/config/aideal-hz23-observer.service.template}"
RENDERED_UNIT="${AIDEAL_HZ23_RENDERED_UNIT:-${PROJECT_DIR}/run/aideal-hz23-observer.service}"
RUN_USER="${AIDEAL_SERVICE_USER:-$(whoami)}"
BASH_BIN="${AIDEAL_BASH_BIN:-$(command -v bash)}"
PYTHON_BIN="${AIDEAL_BROWSER_PYTHON:-${PROJECT_DIR}/.venv-browser/bin/python}"

if [ -f "$SERVICE_CONFIG" ]; then
  . "$SERVICE_CONFIG"
fi

SERVICE_NAME="${AIDEAL_HZ23_SERVICE_NAME:-}"
SYSTEMD_UNIT_DIR="${AIDEAL_SYSTEMD_UNIT_DIR:-}"
SERVICE_PATH="${SYSTEMD_UNIT_DIR}/${SERVICE_NAME}"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "INSTALL_SKIPPED=PROJECT_DIR_MISSING"
elif [ ! -f "$UNIT_TEMPLATE" ]; then
  echo "INSTALL_SKIPPED=UNIT_TEMPLATE_MISSING"
elif [ -z "$SERVICE_NAME" ] || [ -z "$SYSTEMD_UNIT_DIR" ]; then
  echo "INSTALL_SKIPPED=SERVICE_CONFIG_INCOMPLETE"
else
  cd "$PROJECT_DIR"
  "$PYTHON_BIN" -m py_compile \
    run/hz22_prepare_all_product_page.py \
    run/hz23_scan_current_page.py \
    run/hz23_finalize_round.py
  PY_RC=$?
  "$BASH_BIN" -n scripts/hz23_mainline_refresh.sh
  "$BASH_BIN" -n scripts/hz23_observation_daemon.sh
  SH_RC=$?
  echo "PY_RC=$PY_RC"
  echo "SH_RC=$SH_RC"

  if [ "$PY_RC" != "0" ] || [ "$SH_RC" != "0" ]; then
    echo "INSTALL_SKIPPED=STATIC_CHECK_FAILED"
  else
    mkdir -p "$(dirname -- "$RENDERED_UNIT")"
    sed \
      -e "s|@@RUN_USER@@|${RUN_USER}|g" \
      -e "s|@@PROJECT_DIR@@|${PROJECT_DIR}|g" \
      -e "s|@@HOME_DIR@@|${HOME}|g" \
      -e "s|@@BASH_BIN@@|${BASH_BIN}|g" \
      -e "s|@@DAY_START@@|${HZ23_DAY_START}|g" \
      -e "s|@@DAY_END@@|${HZ23_DAY_END}|g" \
      -e "s|@@LOOP_SLEEP_MIN@@|${HZ23_LOOP_SLEEP_MIN}|g" \
      -e "s|@@LOOP_SLEEP_MAX@@|${HZ23_LOOP_SLEEP_MAX}|g" \
      "$UNIT_TEMPLATE" > "$RENDERED_UNIT"
    RENDER_RC=$?

    if [ "$RENDER_RC" != "0" ]; then
      echo "INSTALL_SKIPPED=UNIT_RENDER_FAILED"
    else
      sudo install -m 0644 "$RENDERED_UNIT" "$SERVICE_PATH"
      INSTALL_RC=$?
      if [ "$INSTALL_RC" = "0" ]; then
        sudo systemctl daemon-reload
        sudo systemctl enable --now "$SERVICE_NAME"
        sleep 3
      else
        echo "INSTALL_SKIPPED=UNIT_INSTALL_FAILED"
      fi
    fi
  fi

  echo "===== service status ====="
  if ! sudo systemctl status "$SERVICE_NAME" --no-pager -l | sed -n '1,80p'; then
    echo "SERVICE_STATUS_UNAVAILABLE=1"
  fi

  echo "===== SUMMARY ====="
  echo "SERVICE=$SERVICE_NAME"
  echo "SERVICE_PATH=$SERVICE_PATH"
  echo "USER=$RUN_USER"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null)"
  git status --short | head -n 60
fi
