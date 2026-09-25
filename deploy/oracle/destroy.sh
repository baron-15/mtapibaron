#!/usr/bin/env bash
# Tear down what provision.sh created. Terminates the instance (and its boot volume);
# add --network to also delete the subnet, internet gateway and VCN.
set -euo pipefail
NAME=${MTAPI_INSTANCE_NAME:-mtapi}; PROFILE="${OCI_CLI_PROFILE:-DEFAULT}"; NETWORK=0
[ "${1:-}" = "--network" ] && NETWORK=1
OCI_BIN=$(command -v oci || echo "$HOME/.oci/venv/bin/oci")
oci() { "$OCI_BIN" --profile "$PROFILE" "$@"; }
C=$(awk -F= -v p="[$PROFILE]" '$0==p{f=1;next} /^\[/{f=0} f&&$1~/^ *tenancy *$/{gsub(/ /,"",$2);print $2;exit}' "$HOME/.oci/config")
notnull() { [ -n "$1" ] && [ "$1" != "null" ]; }

for state in RUNNING STOPPED PROVISIONING STARTING STOPPING; do
  ID=$(oci compute instance list -c "$C" --display-name "$NAME" --lifecycle-state $state --query 'data[0].id' --raw-output 2>/dev/null || true)
  if notnull "$ID"; then
    echo "==> terminating instance $ID ($state)"
    oci compute instance terminate --instance-id "$ID" --preserve-boot-volume false --force --wait-for-state TERMINATED >/dev/null
  fi
done

if [ "$NETWORK" = 1 ]; then
  VCN=$(oci network vcn list -c "$C" --display-name "${NAME}-vcn" --query 'data[0].id' --raw-output || true)
  if notnull "$VCN"; then
    SUB=$(oci network subnet list -c "$C" --vcn-id "$VCN" --display-name "${NAME}-public" --query 'data[0].id' --raw-output || true)
    notnull "$SUB" && { echo "==> deleting subnet"; oci network subnet delete --subnet-id "$SUB" --force --wait-for-state TERMINATED >/dev/null; }
    RT=$(oci network vcn get --vcn-id "$VCN" --query 'data."default-route-table-id"' --raw-output)
    oci network route-table update --rt-id "$RT" --route-rules '[]' --force >/dev/null
    IGW=$(oci network internet-gateway list -c "$C" --vcn-id "$VCN" --query 'data[0].id' --raw-output || true)
    notnull "$IGW" && { echo "==> deleting internet gateway"; oci network internet-gateway delete --ig-id "$IGW" --force --wait-for-state TERMINATED >/dev/null; }
    echo "==> deleting VCN"; oci network vcn delete --vcn-id "$VCN" --force --wait-for-state TERMINATED >/dev/null
  fi
fi
echo "done"
