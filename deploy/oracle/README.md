# Running the API on Oracle Cloud (Always Free) as a backup to Render

This directory provisions one Oracle Cloud "Always Free" VM that runs this API behind
[Caddy](https://caddyserver.com) with automatic HTTPS, from a fresh clone of this repo.
It is meant as a second, independent host next to Render, not a replacement.

Files:

| File | Runs where | Purpose |
|---|---|---|
| `provision.sh` | your Mac | Creates the network and the VM with the OCI CLI, retrying while Oracle is out of Arm capacity |
| `cloud-init.yaml` | the VM, first boot | Installs Python 3.10 (via uv), clones the repo, runs gunicorn under systemd, opens the host firewall, installs Caddy |
| `update.sh` | your Mac | SSHes in and deploys the latest commit of the deployed branch |
| `destroy.sh` | your Mac | Terminates the VM (and, with `--network`, the VCN) |

<!-- FACTS -->

## 1. Create the Oracle Cloud account (you, in a browser)

Sign up at <https://www.oracle.com/cloud/free/>. Things that matter at this step and cannot be changed later:

- **Home region.** Always Free compute can only be created in your home region, and the home region is permanent. Pick one near your users where Arm (A1) capacity is reported as available (see the facts section above); avoid the most crowded ones.
- **Payment card.** Oracle requires a real credit or debit card for identity verification and places a small temporary authorization. Prepaid and virtual cards are usually rejected, as are name/address mismatches with the card. Nothing is charged while you stay on the free tier.
- Signup can take a day or two to be approved, and a rejected signup ("we're unable to complete your sign up") is common; retrying later or with a different card often works.

## 2. Give the CLI access (one time, ~5 minutes)

The OCI CLI is a Python package, so it installs without Homebrew. `provision.sh` does this
automatically if it cannot find `oci`, but doing it by hand first lets you check the login:

```bash
python3 -m venv ~/.oci/venv && ~/.oci/venv/bin/pip install oci-cli
```

Then create an API signing key and config. The interactive setup writes `~/.oci/config`
and generates the key pair for you:

```bash
~/.oci/venv/bin/oci setup config
```

It asks for:

- **user OCID** – Console → profile icon (top right) → *My profile* → copy the OCID.
- **tenancy OCID** – profile icon → *Tenancy: \<name\>* → copy the OCID.
- **region** – your home region identifier, e.g. `us-ashburn-1` (shown top right in the console).
- **generate a new API key?** – yes; accept the default paths (`~/.oci/oci_api_key.pem`).

Finally upload the public key it generated: *My profile* → *API keys* → *Add API key* →
*Paste a public key* → paste the contents of `~/.oci/oci_api_key_public.pem`. Check it works:

```bash
~/.oci/venv/bin/oci iam region list --output table
```

(The console's "Add API key → Generate API key pair" button does the same thing in the other
order: download the private key, save it as `~/.oci/oci_api_key.pem`, `chmod 600` it, and paste the
config snippet the console shows into `~/.oci/config`.)

## 3. Provision the VM

```bash
deploy/oracle/provision.sh --email you@example.com --wait
```

- Default shape is **VM.Standard.A1.Flex with 1 OCPU / 6 GB** (Arm). That leaves 3 OCPU / 18 GB of
  the Always Free allowance unused for other things. Change with `--ocpus`/`--memory`.
- Arm capacity is frequently exhausted ("Out of host capacity"). The script cycles through every
  availability domain and retries about once a minute, 30 attempts by default (`--attempts`).
  You can stop it and re-run later; everything it already created is reused.
- If you cannot get Arm capacity, `--shape micro` launches a **VM.Standard.E2.1.Micro**
  (x86, 1/8 OCPU, 1 GB RAM), which is almost always available and is plenty for this API.
- `--email` is passed to Let's Encrypt for expiry notices. Optional but recommended.
- `--dry-run` shows what would be created and the rendered cloud-init without touching anything.

The script prints the public IP and, with `--wait`, polls until `https://<host>/routes` answers.
First boot takes 3–6 minutes (apt, Python download, dependency build, certificate issuance).
Watch it live with:

```bash
ssh ubuntu@<ip> sudo tail -f /var/log/mtapi-bootstrap.log
```

Without `--domain`, the hostname is `<ip-with-dashes>.sslip.io` (e.g. `129-146-1-2.sslip.io`),
a public wildcard DNS service that needs no registration. With `--domain api.example.com`
Caddy will wait for that name to resolve to the VM, so create the A record right after launch.

## 4. Verify it matches Render

```bash
curl -s https://<host>/routes | head -c 300
curl -s https://<host>/by-id/A31 | python3 -m json.tool | head -40
curl -sI https://<host>/by-id/A31 | grep -i access-control
```

The CORS header comes from the committed `settings.cfg` (`DEBUG = True` → `*`), the same file
Render uses, so responses are byte-for-byte the same modulo timestamps.

## 5. Deploying updates

Push to `main` (or whichever `--branch` you deployed), then:

```bash
deploy/oracle/update.sh            # looks the IP up with the OCI CLI
deploy/oracle/update.sh <ip>       # or pass it
```

On the VM this runs `/usr/local/bin/mtapi-update`: `git reset --hard origin/<branch>`, dependency
sync, `systemctl restart mtapi`, then a health check against `/routes`. Local edits inside
`/opt/mtapibaron` are discarded on purpose; server-specific settings belong in
`/etc/mtapi/settings.cfg` (copy the repo's `settings.cfg` there, edit it, uncomment the
`MTAPI_SETTINGS` line in `/etc/mtapi/mtapi.env`, restart).

## 6. Operating it

| Task | Command (on the VM) |
|---|---|
| API logs | `journalctl -u mtapi -f` |
| Caddy / certificate logs | `journalctl -u caddy -f` |
| First-boot log | `sudo cat /var/log/mtapi-bootstrap.log` |
| Re-run the whole bootstrap (idempotent) | `sudo /usr/local/bin/mtapi-bootstrap` |
| Current hostname | `cat /etc/mtapi/domain` |
| Restart the API | `sudo systemctl restart mtapi` |

The service runs **one gunicorn worker with 8 threads** deliberately: the feed cache and the
background refresh thread live inside the process, so more workers would each poll the MTA.

Tear everything down with `deploy/oracle/destroy.sh` (instance and boot volume) or
`deploy/oracle/destroy.sh --network` (also the subnet, gateway and VCN).

## 7. Using it as a failover from the frontend

The frontend hardcodes one API base URL. To make the Oracle host a real backup, have the fetch
fall back to the second host when the first one fails or times out, for example:

```js
const API_HOSTS = ['https://<render-host>', 'https://<oracle-host>'];
async function fetchStation(id) {
  for (const host of API_HOSTS) {
    try {
      const r = await fetch(`${host}/by-id/${id}`, { signal: AbortSignal.timeout(8000) });
      if (r.ok) return r.json();
    } catch (_) { /* try the next host */ }
  }
  throw new Error('all API hosts failed');
}
```

## Gotchas specific to Oracle Cloud

- **Two firewalls.** Traffic must be allowed both in the VCN security list (done by `provision.sh`)
  and in the instance's own iptables, which Oracle's Ubuntu images ship with a REJECT rule after
  port 22 (done by `cloud-init.yaml`). Forgetting the second one is the classic "security list is
  open but nothing connects" problem.
- **The public IP is ephemeral but stable**: it stays with the instance for its lifetime, including
  reboots, and changes only if the instance is terminated and recreated. A reserved IP is also free
  if you want one that survives recreation.
- **Idle reclamation** applies to Always Free tenancies; see the facts section above for the current
  thresholds and the Pay-As-You-Go upgrade that removes the rule.
- **sslip.io shares Let's Encrypt rate limits** with everyone else using it; Caddy falls back to
  ZeroSSL automatically, but a domain you control is the more robust choice long term.
