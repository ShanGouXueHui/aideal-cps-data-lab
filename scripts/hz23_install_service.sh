#!/usr/bin/env bash
# Install HZ23 observer as a system service owned by the current user.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
SERVICE_NAME="aideal-hz23-observer.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"
RUN_USER="$(whoami)"

cd "$PROJECT_DIR" || exit 1

echo "===== static checks ====="
.venv-browser/bin/python -m py_compile \
  run/hz22_prepare_all_product_page.py \
  run/hz23_scan_current_page.py \
  run/hz23_finalize_round.py
PY_RC=$?
bash -n scripts/hz21_run_strong_risk_collector.sh
bash -n scripts/hz23_mainline_refresh.sh
bash -n scripts/hz23_observation_daemon.sh
SH_RC=$?
echo "PY_RC=$PY_RC"
echo "SH_RC=$SH_RC"

if [ "$PY_RC" != "0" ] || [ "$SH_RC" != "0" ]; then
  echo "INSTALL_SKIPPED=STATIC_CHECK_FAILED"
else
  sudo tee "$SERVICE_PATH" >/dev/null <<EOF
[Unit]
Description=AIdeal CPS HZ23 JD catalog observation daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${PROJECT_DIR}
Environment=HOME=${HOME}
Environment=PYTHONUNBUFFERED=1
Environment=HZ23_DAY_START=09:30
Environment=HZ23_DAY_END=21:30
Environment=HZ23_LOOP_SLEEP_MIN=240
Environment=HZ23_LOOP_SLEEP_MAX=480
ExecStart=/usr/bin/bash ${PROJECT_DIR}/scripts/hz23_observation_daemon.sh
Restart=always
RestartSec=30
KillSignal=SIGTERM
TimeoutStopSec=45

[Install]
WantedBy=multi-user.target
EOF

  sudo systemctl daemon-reload
  sudo systemctl enable --now "$SERVICE_NAME"
  sleep 3
fi

echo "===== service status ====="
sudo systemctl status "$SERVICE_NAME" --no-pager -l | sed -n '1,80p' || true

echo "===== SUMMARY ====="
echo "SERVICE=$SERVICE_NAME"
echo "SERVICE_PATH=$SERVICE_PATH"
echo "USER=$RUN_USER"
echo "PROJECT_DIR=$PROJECT_DIR"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
git status --short | head -n 60
