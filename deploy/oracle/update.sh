#!/usr/bin/env bash
# Deploy the latest commit of the deployed branch to the Oracle VM and restart the API.
# Usage: deploy/oracle/update.sh [PUBLIC_IP]   (IP is looked up via the OCI CLI when omitted)
set -euo pipefail
NAME=${MTAPI_INSTANCE_NAME:-mtapi}
IP=${1:-}
if [ -z "$IP" ]; then
  OCI_BIN=$(command -v oci || echo "$HOME/.oci/venv/bin/oci")
  [ -x "$OCI_BIN" ] || { echo "pass the VM's public IP: $0 <ip>" >&2; exit 1; }
  ID=$("$OCI_BIN" --profile "${OCI_CLI_PROFILE:-DEFAULT}" compute instance list --display-name "$NAME" --lifecycle-state RUNNING \
        -c "$(awk -F= '/^tenancy/{gsub(/ /,"",$2);print $2;exit}' "$HOME/.oci/config")" --query 'data[0].id' --raw-output)
  IP=$("$OCI_BIN" --profile "${OCI_CLI_PROFILE:-DEFAULT}" compute instance list-vnics --instance-id "$ID" --query 'data[0]."public-ip"' --raw-output)
fi
echo "==> updating mtapi on $IP"
ssh -o StrictHostKeyChecking=accept-new "ubuntu@$IP" sudo /usr/local/bin/mtapi-update
