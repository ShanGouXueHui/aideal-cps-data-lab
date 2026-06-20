#!/usr/bin/env bash
# Run Data Lab validation on the Singapore datalab account from Hangzhou.
# No set -e is used.

ACTION="${1:-validate-publish}"
SG_HOST="${SG_HOST:-43.106.55.255}"
SG_PORT="${SG_PORT:-22}"
SG_USER="${SG_USER:-datalab}"
SG_REPO="${SG_REPO:-/home/datalab/projects/aideal-cps-data-lab}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519_aideal_datalab_bridge}"
SSH_CONFIG="${SSH_CONFIG:-$HOME/.ssh/config}"
SSH_ALIAS="${SSH_ALIAS:-sg-aideal-datalab}"

print_summary() {
  echo "===== HANGZHOU BRIDGE SUMMARY ====="
  echo "ACTION=$ACTION"
  echo "SG_HOST=$SG_HOST"
  echo "SG_USER=$SG_USER"
  echo "SG_REPO=$SG_REPO"
  echo "SSH_KEY=$SSH_KEY"
}

write_ssh_config() {
  mkdir -p "$HOME/.ssh"
  chmod 0700 "$HOME/.ssh"
  touch "$SSH_CONFIG"
  chmod 0600 "$SSH_CONFIG"

  if grep -q "^Host ${SSH_ALIAS}$" "$SSH_CONFIG" 2>/dev/null; then
    return 0
  fi

  {
    printf '\nHost %s\n' "$SSH_ALIAS"
    printf '    HostName %s\n' "$SG_HOST"
    printf '    Port %s\n' "$SG_PORT"
    printf '    User %s\n' "$SG_USER"
    printf '    IdentityFile %s\n' "$SSH_KEY"
    printf '    IdentitiesOnly yes\n'
    printf '    ServerAliveInterval 30\n'
    printf '    ServerAliveCountMax 3\n'
  } >> "$SSH_CONFIG"
}

bootstrap() {
  mkdir -p "$HOME/.ssh"
  chmod 0700 "$HOME/.ssh"

  if [ ! -f "$SSH_KEY" ]; then
    ssh-keygen \
      -t ed25519 \
      -f "$SSH_KEY" \
      -N "" \
      -C "aideal-datalab-bridge@hangzhou"
    KEY_RC=$?
    if [ "$KEY_RC" != "0" ]; then
      echo "STATUS=FAIL"
      echo "REASON=ssh_key_generation_failed"
      return 1
    fi
  fi

  chmod 0600 "$SSH_KEY"
  chmod 0644 "${SSH_KEY}.pub"
  write_ssh_config
  CONFIG_RC=$?
  if [ "$CONFIG_RC" != "0" ]; then
    echo "STATUS=FAIL"
    echo "REASON=ssh_config_failed"
    return 1
  fi

  print_summary
  echo "STATUS=KEY_READY"
  echo "PUBLIC_KEY_BEGIN"
  cat "${SSH_KEY}.pub"
  echo "PUBLIC_KEY_END"
  echo "NEXT_STEP=Add this public key to /home/datalab/.ssh/authorized_keys on Singapore once."
  return 0
}

check_connection() {
  ssh \
    -o BatchMode=yes \
    -o StrictHostKeyChecking=accept-new \
    "$SSH_ALIAS" \
    "printf 'REMOTE_USER=%s\\nREMOTE_HOME=%s\\n' \"\$(id -un)\" \"\$HOME\"; test -d '$SG_REPO/.git'"
  SSH_RC=$?
  if [ "$SSH_RC" != "0" ]; then
    print_summary
    echo "STATUS=FAIL"
    echo "REASON=singapore_ssh_or_repository_unavailable"
    echo "RUN_BOOTSTRAP=bash $0 bootstrap"
    return 1
  fi
  print_summary
  echo "STATUS=PASS"
  return 0
}

run_remote() {
  REMOTE_ACTION="$1"
  check_connection >/tmp/aideal_datalab_bridge_check.log 2>&1
  CHECK_RC=$?
  if [ "$CHECK_RC" != "0" ]; then
    cat /tmp/aideal_datalab_bridge_check.log
    return 1
  fi

  ssh \
    -o BatchMode=yes \
    "$SSH_ALIAS" \
    "cd '$SG_REPO' && bash scripts/ops/run_data_lab_remote_worker.sh '$REMOTE_ACTION'"
  REMOTE_RC=$?
  print_summary
  echo "REMOTE_ACTION=$REMOTE_ACTION"
  echo "REMOTE_RC=$REMOTE_RC"
  if [ "$REMOTE_RC" = "0" ]; then
    echo "STATUS=PASS"
  else
    echo "STATUS=FAIL"
  fi
  return "$REMOTE_RC"
}

case "$ACTION" in
  bootstrap)
    bootstrap
    exit $?
    ;;
  check)
    check_connection
    exit $?
    ;;
  validate)
    run_remote validate
    exit $?
    ;;
  validate-publish)
    run_remote validate-publish
    exit $?
    ;;
  publish-reports)
    run_remote publish-reports
    exit $?
    ;;
  *)
    echo "STATUS=FAIL"
    echo "REASON=unknown_action"
    echo "SUPPORTED_ACTIONS=bootstrap check validate validate-publish publish-reports"
    exit 2
    ;;
esac
