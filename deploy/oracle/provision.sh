#!/usr/bin/env bash
# Provision an Oracle Cloud "Always Free" VM that runs mtapibaron behind Caddy (HTTPS).
#
# Prerequisites (one time, see README.md):
#   1. An Oracle Cloud account and an API signing key: `oci setup config`
#   2. An SSH public key in ~/.ssh (id_ed25519.pub or id_rsa.pub)
#
# Usage:
#   deploy/oracle/provision.sh [options]
#     --shape a1|micro      a1 = VM.Standard.A1.Flex (Arm, default), micro = VM.Standard.E2.1.Micro (x86, 1 GB)
#     --ocpus N             A1 OCPUs (default 1; Always Free total is 4)
#     --memory GB           A1 memory (default 6; Always Free total is 24)
#     --domain HOST         hostname for HTTPS; default: <public-ip>.sslip.io (no DNS setup needed)
#     --email ADDR          contact email for Let's Encrypt (optional, recommended)
#     --ad NAME             pin one availability domain (default: try them all)
#     --attempts N          launch attempts across ADs before giving up (default 30, ~60 s apart)
#     --compartment OCID    default: the tenancy root compartment
#     --profile NAME        ~/.oci/config profile (default: $OCI_CLI_PROFILE or DEFAULT)
#     --name NAME           instance/display-name prefix (default mtapi)
#     --repo URL            git repo the VM clones (default https://github.com/baron-15/mtapibaron.git)
#     --branch NAME         branch to deploy (default main)
#     --ssh-key PATH        public key to authorize (default: first of ~/.ssh/id_ed25519.pub, ~/.ssh/id_rsa.pub)
#     --wait                after launch, poll the HTTPS endpoint until it answers (up to 10 min)
#     --dry-run             print what would be created and exit before touching the cloud
#
# Re-running is safe: existing network pieces and a RUNNING instance with the same name are reused.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
SHAPE_KIND=a1; OCPUS=1; MEMORY_GB=6; DOMAIN=""; ACME_EMAIL=""; AD_PIN=""; ATTEMPTS=30; SLEEP_BETWEEN=60
PROFILE="${OCI_CLI_PROFILE:-DEFAULT}"; COMPARTMENT=""; NAME=mtapi; BRANCH=main
REPO_URL=https://github.com/baron-15/mtapibaron.git; SSH_KEY=""; BOOT_GB=50; UBUNTU_VERSION=24.04
WAIT=0; DRY_RUN=0

die() { echo "error: $*" >&2; exit 1; }
info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --shape) SHAPE_KIND=$2; shift 2;;
    --ocpus) OCPUS=$2; shift 2;;
    --memory) MEMORY_GB=$2; shift 2;;
    --domain) DOMAIN=$2; shift 2;;
    --email) ACME_EMAIL=$2; shift 2;;
    --ad) AD_PIN=$2; shift 2;;
    --attempts) ATTEMPTS=$2; shift 2;;
    --compartment) COMPARTMENT=$2; shift 2;;
    --profile) PROFILE=$2; shift 2;;
    --name) NAME=$2; shift 2;;
    --repo) REPO_URL=$2; shift 2;;
    --branch) BRANCH=$2; shift 2;;
    --ssh-key) SSH_KEY=$2; shift 2;;
    --wait) WAIT=1; shift;;
    --dry-run) DRY_RUN=1; shift;;
    -h|--help) sed -n '2,30p' "$0"; exit 0;;
    *) die "unknown option $1 (try --help)";;
  esac
done

case "$SHAPE_KIND" in
  a1)    SHAPE=VM.Standard.A1.Flex; SHAPE_CONFIG="{\"ocpus\": $OCPUS, \"memoryInGBs\": $MEMORY_GB}";;
  micro) SHAPE=VM.Standard.E2.1.Micro; SHAPE_CONFIG="";;
  *) die "--shape must be a1 or micro";;
esac

# ---------------------------------------------------------------- tooling
command -v python3 >/dev/null || die "python3 is required"
OCI_BIN=$(command -v oci || true)
[ -n "$OCI_BIN" ] || { [ -x "$HOME/.oci/venv/bin/oci" ] && OCI_BIN="$HOME/.oci/venv/bin/oci"; } || true
if [ -z "$OCI_BIN" ]; then
  info "OCI CLI not found; installing it with pip into ~/.oci/venv (no Homebrew needed)"
  python3 -m venv "$HOME/.oci/venv"
  "$HOME/.oci/venv/bin/pip" install --quiet --upgrade pip oci-cli
  OCI_BIN="$HOME/.oci/venv/bin/oci"
fi
oci() { "$OCI_BIN" --profile "$PROFILE" "$@"; }
[ -f "$HOME/.oci/config" ] || die "no ~/.oci/config. Run:  $OCI_BIN setup config   (README.md walks through it)"

if [ -z "$SSH_KEY" ]; then
  for k in "$HOME/.ssh/id_ed25519.pub" "$HOME/.ssh/id_rsa.pub"; do [ -f "$k" ] && { SSH_KEY=$k; break; }; done
fi
[ -f "${SSH_KEY:-}" ] || die "no SSH public key found; pass --ssh-key"

# ---------------------------------------------------------------- identity
cfg_value() {  # cfg_value <key>  -> value from the selected profile in ~/.oci/config
  awk -F= -v p="[$PROFILE]" '
    $0==p {f=1; next} /^\[/ {f=0}
    f { k=$1; gsub(/[ \t]/,"",k); if (k==key) { v=$2; sub(/^[ \t]+/,"",v); sub(/[ \t]+$/,"",v); print v; exit } }' key="$1" "$HOME/.oci/config"
}
TENANCY=$(cfg_value tenancy); REGION=$(cfg_value region)
[ -n "$TENANCY" ] || die "profile [$PROFILE] in ~/.oci/config has no tenancy"
COMPARTMENT=${COMPARTMENT:-$TENANCY}
json() { python3 -c "import json,sys; d=json.load(sys.stdin); $1"; }
notnull() { [ -n "$1" ] && [ "$1" != "null" ]; }

info "region $REGION, compartment ${COMPARTMENT:0:40}..., shape $SHAPE ${SHAPE_CONFIG:+$SHAPE_CONFIG}"
oci iam region list >/dev/null 2>&1 || die "OCI CLI cannot authenticate; check ~/.oci/config and the key file"

# ---------------------------------------------------------------- render cloud-init
RENDERED=$(mktemp -t mtapi-cloud-init.XXXXXX)
trap 'rm -f "$RENDERED"' EXIT
sed -e "s|__DOMAIN__|$DOMAIN|" -e "s|__ACME_EMAIL__|$ACME_EMAIL|" \
    -e "s|__REPO_URL__|$REPO_URL|" -e "s|__BRANCH__|$BRANCH|" "$here/cloud-init.yaml" > "$RENDERED"
grep -q '__[A-Z_]*__' "$RENDERED" && die "unrendered placeholder left in cloud-init"
B64_SIZE=$(base64 < "$RENDERED" | wc -c | tr -d ' ')
[ "$B64_SIZE" -lt 16000 ] || die "cloud-init is $B64_SIZE bytes base64-encoded; OCI user_data must stay under 16 KB"

if [ "$DRY_RUN" = 1 ]; then
  info "dry run: would ensure VCN ${NAME}-vcn / subnet ${NAME}-public, then launch $SHAPE named $NAME"
  info "cloud-init rendered to $RENDERED ($B64_SIZE bytes base64):"; sed -n '1,12p' "$RENDERED"; exit 0
fi

# ---------------------------------------------------------------- existing instance?
EXISTING=$(oci compute instance list -c "$COMPARTMENT" --display-name "$NAME" --lifecycle-state RUNNING \
            --query 'data[0].id' --raw-output 2>/dev/null || true)
if notnull "$EXISTING"; then
  IP=$(oci compute instance list-vnics --instance-id "$EXISTING" --query 'data[0]."public-ip"' --raw-output)
  info "instance '$NAME' already RUNNING ($EXISTING), public IP $IP; nothing to launch"
  echo "ssh ubuntu@$IP   |   https://$( [ -n "$DOMAIN" ] && echo "$DOMAIN" || echo "${IP//./-}.sslip.io" )/routes"
  exit 0
fi

# ---------------------------------------------------------------- network (idempotent by display name)
VCN_ID=$(oci network vcn list -c "$COMPARTMENT" --display-name "${NAME}-vcn" --query 'data[0].id' --raw-output || true)
if ! notnull "$VCN_ID"; then
  info "creating VCN ${NAME}-vcn (10.0.0.0/16)"
  VCN_ID=$(oci network vcn create -c "$COMPARTMENT" --cidr-block 10.0.0.0/16 --display-name "${NAME}-vcn" \
            --dns-label "${NAME//-/}" --wait-for-state AVAILABLE --query data.id --raw-output)
fi
IGW_ID=$(oci network internet-gateway list -c "$COMPARTMENT" --vcn-id "$VCN_ID" --query 'data[0].id' --raw-output || true)
if ! notnull "$IGW_ID"; then
  info "creating internet gateway"
  IGW_ID=$(oci network internet-gateway create -c "$COMPARTMENT" --vcn-id "$VCN_ID" --is-enabled true \
            --display-name "${NAME}-igw" --wait-for-state AVAILABLE --query data.id --raw-output)
fi
RT_ID=$(oci network vcn get --vcn-id "$VCN_ID" --query 'data."default-route-table-id"' --raw-output)
SL_ID=$(oci network vcn get --vcn-id "$VCN_ID" --query 'data."default-security-list-id"' --raw-output)
info "default route 0.0.0.0/0 -> internet gateway"
oci network route-table update --rt-id "$RT_ID" --force --wait-for-state AVAILABLE \
  --route-rules "[{\"destination\":\"0.0.0.0/0\",\"destinationType\":\"CIDR_BLOCK\",\"networkEntityId\":\"$IGW_ID\"}]" >/dev/null
info "security list: allow TCP 22, 80, 443 from anywhere"
tcp_rule() { printf '{"protocol":"6","source":"0.0.0.0/0","sourceType":"CIDR_BLOCK","isStateless":false,"tcpOptions":{"destinationPortRange":{"min":%s,"max":%s}}}' "$1" "$1"; }
INGRESS="[$(tcp_rule 22),$(tcp_rule 80),$(tcp_rule 443),"
INGRESS+='{"protocol":"1","source":"0.0.0.0/0","sourceType":"CIDR_BLOCK","isStateless":false,"icmpOptions":{"type":3,"code":4}},'
INGRESS+='{"protocol":"1","source":"10.0.0.0/16","sourceType":"CIDR_BLOCK","isStateless":false,"icmpOptions":{"type":3}}]'
oci network security-list update --security-list-id "$SL_ID" --force --wait-for-state AVAILABLE \
  --ingress-security-rules "$INGRESS" >/dev/null
SUBNET_ID=$(oci network subnet list -c "$COMPARTMENT" --vcn-id "$VCN_ID" --display-name "${NAME}-public" --query 'data[0].id' --raw-output || true)
if ! notnull "$SUBNET_ID"; then
  info "creating public subnet ${NAME}-public (10.0.0.0/24)"
  SUBNET_ID=$(oci network subnet create -c "$COMPARTMENT" --vcn-id "$VCN_ID" --cidr-block 10.0.0.0/24 \
               --display-name "${NAME}-public" --dns-label pub --wait-for-state AVAILABLE --query data.id --raw-output)
fi

# ---------------------------------------------------------------- image + availability domains
info "looking up the newest Canonical Ubuntu $UBUNTU_VERSION image for $SHAPE"
IMAGE_ID=$(oci compute image list -c "$COMPARTMENT" --operating-system "Canonical Ubuntu" \
  --operating-system-version "$UBUNTU_VERSION" --shape "$SHAPE" --sort-by TIMECREATED --sort-order DESC --all \
  | json 'imgs=[i for i in d["data"] if "Minimal" not in i["display-name"]] or d["data"]; print(imgs[0]["id"] if imgs else "")')
notnull "$IMAGE_ID" || die "no Canonical Ubuntu $UBUNTU_VERSION image found for $SHAPE in $REGION"

ADS=()
if [ -n "$AD_PIN" ]; then ADS=("$AD_PIN"); else
  while IFS= read -r ad; do [ -n "$ad" ] && ADS+=("$ad"); done \
    < <(oci iam availability-domain list -c "$COMPARTMENT" | json 'print("\n".join(a["name"] for a in d["data"]))')
fi
[ ${#ADS[@]} -gt 0 ] || die "no availability domains returned"
info "availability domains: ${ADS[*]}"

# ---------------------------------------------------------------- launch (retry on "Out of host capacity")
INSTANCE_ID=""; attempt=0
while [ -z "$INSTANCE_ID" ] && [ $attempt -lt "$ATTEMPTS" ]; do
  for ad in "${ADS[@]}"; do
    attempt=$((attempt+1))
    info "attempt $attempt/$ATTEMPTS: launching $SHAPE in $ad"
    set +e
    OUT=$(oci compute instance launch -c "$COMPARTMENT" --availability-domain "$ad" --shape "$SHAPE" \
          ${SHAPE_CONFIG:+--shape-config "$SHAPE_CONFIG"} --image-id "$IMAGE_ID" --subnet-id "$SUBNET_ID" \
          --assign-public-ip true --display-name "$NAME" --hostname-label "$NAME" \
          --boot-volume-size-in-gbs "$BOOT_GB" --ssh-authorized-keys-file "$SSH_KEY" --user-data-file "$RENDERED" \
          --wait-for-state RUNNING --wait-for-state TERMINATED --max-wait-seconds 900 2>&1)
    rc=$?
    set -e
    if [ $rc -eq 0 ]; then
      INSTANCE_ID=$(printf '%s' "$OUT" | json 'print(d["data"]["id"])')
      STATE=$(printf '%s' "$OUT" | json 'print(d["data"]["lifecycle-state"])')
      [ "$STATE" = RUNNING ] || die "instance $INSTANCE_ID ended in state $STATE; check the console"
      break
    fi
    if printf '%s' "$OUT" | grep -qi 'out of.*capacity'; then
      echo "    no free $SHAPE capacity in $ad right now"
    elif printf '%s' "$OUT" | grep -qi 'LimitExceeded\|service limit'; then
      die "service limit hit: $(printf '%s' "$OUT" | tail -3). Always Free allows 4 OCPU/24 GB of A1 and 2 Micro instances in total."
    else
      die "launch failed for a reason other than capacity:
$OUT"
    fi
    [ $attempt -lt "$ATTEMPTS" ] || break
  done
  [ -n "$INSTANCE_ID" ] || { echo "    sleeping ${SLEEP_BETWEEN}s before retrying (Ctrl-C to stop; re-running later is safe)"; sleep "$SLEEP_BETWEEN"; }
done
[ -n "$INSTANCE_ID" ] || die "gave up after $ATTEMPTS attempts. Try later, another --ad, or --shape micro (x86, 1 GB) which is usually available."

IP=$(oci compute instance list-vnics --instance-id "$INSTANCE_ID" --query 'data[0]."public-ip"' --raw-output)
HOST=${DOMAIN:-${IP//./-}.sslip.io}
cat <<EOF

Instance   $INSTANCE_ID
Public IP  $IP
SSH        ssh ubuntu@$IP
Bootstrap  ssh ubuntu@$IP sudo tail -f /var/log/mtapi-bootstrap.log     (takes ~3-6 minutes)
API        https://$HOST/routes
Update     deploy/oracle/update.sh $IP
EOF
[ -n "$DOMAIN" ] && echo "DNS        create an A record  $DOMAIN -> $IP  now; Caddy keeps retrying certificate issuance until it resolves."

if [ "$WAIT" = 1 ]; then
  info "waiting for https://$HOST/routes"
  for _ in $(seq 1 60); do
    if curl -sf --max-time 10 "https://$HOST/routes" >/dev/null 2>&1; then info "API is up: https://$HOST/routes"; exit 0; fi
    sleep 10
  done
  echo "not answering yet; check the bootstrap log over SSH" >&2; exit 1
fi
