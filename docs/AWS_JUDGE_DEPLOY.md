# AWS dedicated-host alternative

**Current hosting reuses an existing server:** see [the shared-host deployment](LIGHTSAIL_SHARED_HOST.md). Do not run this dedicated-host plan on that shared server.

**Earlier 8 November dedicated-host attempt: provisioned, then cleaned up.** One $7/month
Lightsail host and attached static IP were created under the existing AWS
allowance. SSH preparation stopped after two failures: the local helper assumed
an optional API field; the corrected helper then rejected an empty `hostKeys`
list. No SSH connection, image build, application upload or public TLS check
occurred. The unused instance was deleted and its address released. Brief
provisioning may incur a small charge; its actual billed amount is not yet known.
[Attempt and cleanup evidence](../evidence/runs/submission-ready/aws-attempt-nov8.json).

The latest product is runnable with `./scripts/judge.sh`. The existing
[Pages demo](https://himanshu748.github.io/crashcart/) remains available on an
older release; GitHub's account billing lock prevents its current workflow from
starting. The new shared-host address is verified separately; the failure below remains historical.

Hosting is optional; a complete runnable local path is accepted. AWS is not a
submission gate. Follow [current access and freeze guidance](RULES_READINESS.md).

## Cost and lifetime

The selected `micro_3_0` Linux/public-IPv4 bundle in `us-east-1` is **$7/month
base**, 1 GB RAM, 40 GB disk and 2 TB transfer. No snapshots, CDN, database,
load balancer or domain purchase is included. Taxes and transfer overage can
increase the total; the $10 allowance is not a provider-enforced spending cap.
An attached static IP is included; release an unused detached address promptly.
[AWS pricing](https://aws.amazon.com/lightsail/pricing/).

The existing `CrashCart-account-monthly-alerts` budget has monthly ACTUAL
notifications above $20 and $50. Both configurations read back `OK` on 8 November;
email delivery is untested. They cover the whole account, including other projects,
and are alerts, not hard caps. Do not create duplicate budgets.

A successful deployment must retain its instance, IP and certificate volumes
through **22 December 2026 UTC**. No scheduled teardown is installed. Daily checks
and certificate renewal remain operational responsibilities; future availability
cannot be established by one test. Remove resources only after judging, on or
after 23 December UTC. Stopping a Lightsail instance does not eliminate its bill.

## Reproducible commands for a resumed deployment

These are prepared commands, **not a completed hosted result**. Do not rerun the
stopped SSH step automatically. First obtain a fresh API response containing
host-key evidence or verify the server fingerprint through the Lightsail console.
Never disable SSH host verification or bypass a TLS warning. Stop if a step fails
twice and retain its failure.

Run from a reviewed public clone on your Mac with AWS CLI v2, Python 3.11+,
OpenSSH and the intended account already authenticated. Do not create or upload
AWS access keys. The state directory below contains temporary SSH credentials;
keep it outside the repository. No PayPal, KERNEL, model or licence key belongs
on this host. TLS/SSH host private keys are necessary infrastructure keys.

```sh
set -eu
export AWS_REGION=us-east-1 AWS_PAGER=''
export CC_INSTANCE=crashcart-judge-20261108
export CC_STATIC_IP=crashcart-judge-ip-20261108
export CC_STATE=$(mktemp -d)
chmod 700 "$CC_STATE"
export CC_RELEASE=$(git rev-parse HEAD)
export CC_ADMIN_CIDR="$(curl -fsS https://checkip.amazonaws.com)/32"
date -u
aws lightsail get-bundles --region "$AWS_REGION" --no-include-inactive \
  --query "bundles[?bundleId=='micro_3_0'].[bundleId,price,ramSizeInGb]"
# Continue only if the active Linux plan is micro_3_0, USD7, 1GB.
aws lightsail create-instances --region "$AWS_REGION" \
  --instance-names "$CC_INSTANCE" --availability-zone us-east-1a \
  --blueprint-id ubuntu_24_04 --bundle-id micro_3_0 --ip-address-type ipv4 \
  --user-data file://deploy/judge/bootstrap.sh \
  --tags key=Project,value=CrashCart key=Purpose,value=Recorded-judge-demo \
         key=RetainThrough,value=2026-12-22 key=MonthlyBaseUSD,value=7
aws lightsail get-instance --region "$AWS_REGION" --instance-name "$CC_INSTANCE" \
  --query 'instance.[state.name,bundleId,blueprintId]'
# Wait for running; read back, do not create another instance.
aws lightsail put-instance-public-ports --region "$AWS_REGION" \
  --instance-name "$CC_INSTANCE" --port-infos \
  "[{\"fromPort\":22,\"toPort\":22,\"protocol\":\"tcp\",\"cidrs\":[\"$CC_ADMIN_CIDR\"]},{\"fromPort\":80,\"toPort\":80,\"protocol\":\"tcp\",\"cidrs\":[\"0.0.0.0/0\"]},{\"fromPort\":443,\"toPort\":443,\"protocol\":\"tcp\",\"cidrs\":[\"0.0.0.0/0\"]}]"
aws lightsail allocate-static-ip --region "$AWS_REGION" --static-ip-name "$CC_STATIC_IP"
aws lightsail attach-static-ip --region "$AWS_REGION" \
  --static-ip-name "$CC_STATIC_IP" --instance-name "$CC_INSTANCE"
export JUDGE_ADDRESS=$(aws lightsail get-static-ip --region "$AWS_REGION" \
  --static-ip-name "$CC_STATIC_IP" --query staticIp.ipAddress --output text)
umask 077
aws lightsail get-instance-access-details --region "$AWS_REGION" \
  --instance-name "$CC_INSTANCE" --protocol ssh > "$CC_STATE/access.json"
python3 - <<'PY'
import json, os, pathlib, ipaddress
p = pathlib.Path(os.environ['CC_STATE'])
a = json.loads((p/'access.json').read_text())['accessDetails']
ipaddress.IPv4Address(a['ipAddress'])
assert a['ipAddress'] == os.environ['JUDGE_ADDRESS']
assert a.get('hostKeys'), 'No AWS host-key evidence: STOP; do not bypass verification'
assert a.get('privateKey') and a.get('certKey')
for name, value in [('access', a['privateKey']), ('access-cert.pub', a['certKey'])]:
    f = p/name; f.write_text(value+'\n'); f.chmod(0o600)
keys = []
for k in a['hostKeys']:
    key = k['publicKey']
    if not key.startswith(('ssh-', 'ecdsa-')):
        key = k['algorithm']+' '+key
    keys.append(a['ipAddress']+' '+key)
(p/'known_hosts').write_text('\n'.join(keys)+'\n')
PY
cc_ssh() {
  ssh -i "$CC_STATE/access" -o "CertificateFile=$CC_STATE/access-cert.pub" \
    -o "UserKnownHostsFile=$CC_STATE/known_hosts" -o StrictHostKeyChecking=yes \
    -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15 \
    "ubuntu@$JUDGE_ADDRESS" "$@"
}
cc_ssh 'set -eu; cloud-init status --wait; sudo docker compose version; sudo docker buildx version; sudo swapon --show'
```

Wait for cloud-init completion and inspect failures before building. The bootstrap
installs Ubuntu Docker/Compose/Buildx and a bounded 1 GB swap file on the included
disk. Its latest version is source-reviewed and shell-syntax checked; this
attempt did not verify its execution. The earlier Caddy configuration used
`JUDGE_DOMAIN` and `ACME_EMAIL`; the current one uses only **`JUDGE_ADDRESS`**.

On the new host, clone public source only, detach at the reviewed pushed commit,
and build. Replace the two explicit placeholders with the values from your Mac.

```sh
# Run these inside the verified SSH connection.
set -eu
sudo apt-get install -y git
git clone https://github.com/himanshu748/crashcart.git crashcart-judge
cd crashcart-judge
git checkout --detach REVIEWED_FULL_COMMIT
export JUDGE_ADDRESS=OWNED_STATIC_IPV4
sudo env JUDGE_ADDRESS="$JUDGE_ADDRESS" docker compose -f deploy/judge/compose.yaml config --quiet
sudo env JUDGE_ADDRESS="$JUDGE_ADDRESS" docker compose -f deploy/judge/compose.yaml build --pull
sudo env JUDGE_ADDRESS="$JUDGE_ADDRESS" docker compose -f deploy/judge/compose.yaml run --rm --no-deps judge \
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo env JUDGE_ADDRESS="$JUDGE_ADDRESS" docker compose -f deploy/judge/compose.yaml up -d --no-build
sudo docker image inspect crashcart-judge:reviewed --format '{{.Id}}'
```

Caddy is pinned to `2.11.9-alpine`, with an explicit Let's Encrypt issuer and
`shortlived` profile. This enables a public-IP certificate without buying a
domain or supplying a contact email. IP certificates last 160 hours, so
persistent `/data`, running renewal and reachable ports 80/443 are essential.
Do not run `down -v`. Runtime contains static exported assets only, no Python
service or provider adapter. Image tags still resolve at build time; record the
base digests and final image ID. [Caddy TLS configuration](https://caddyserver.com/docs/caddyfile/directives/tls),
[Let's Encrypt IP certificates](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability).

## Before sharing the address

From the Mac, with normal certificate verification (no `-k`):

```sh
curl -fSsI "https://$JUDGE_ADDRESS/"
curl -fSs "https://$JUDGE_ADDRESS/data.json" -o "$CC_STATE/hosted-data.json"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "https://$JUDGE_ADDRESS/"
curl -sS -o /dev/null -w '%{http_code}\n' "https://$JUDGE_ADDRESS/.env"
curl -fSs "https://$JUDGE_ADDRESS/downloads/replay.zip" -o "$CC_STATE/replay.zip"
python3 -m zipfile -t "$CC_STATE/replay.zip"
```

Require trusted HTTPS200, POST405, `.env`404, defective
`FAIL/paid_without_ticket/0`, healthy `PASS/ticket_delivered_once_on_time/1`,
`mode=RECORDED_REPLAY`, `computed_when=site build`, `network_calls=0` and
`fresh_execution=false`. Verify the historical AI separate-case labels. Download
and execute the ZIP, not just its integrity check. Exercise all three AI steps,
case switch, filters, keyboard, reduced motion and phone layout in a real browser.
Save source hashes, image ID, certificate details and screenshots. A source
review, isolated export or old container result does not establish these checks.

## Cleanup after judging or an abandoned empty deployment

Only target this dedicated named instance and its attached address after verifying
ownership/tags. Never delete other projects. For a deployed demo, wait until
23 December 2026 UTC; an unused failed attempt can be cleaned up immediately.

```sh
aws lightsail delete-instance --region "$AWS_REGION" --instance-name "$CC_INSTANCE"
aws lightsail get-static-ip --region "$AWS_REGION" --static-ip-name "$CC_STATIC_IP" \
  --query 'staticIp.[isAttached,attachedTo]'
# Release only after readback confirms detached.
aws lightsail release-static-ip --region "$AWS_REGION" --static-ip-name "$CC_STATIC_IP"
aws lightsail get-instances --region "$AWS_REGION" --query "instances[?name=='$CC_INSTANCE'].name"
aws lightsail get-static-ips --region "$AWS_REGION" --query "staticIps[?name=='$CC_STATIC_IP'].name"
rm -f "$CC_STATE/access.json" "$CC_STATE/access" "$CC_STATE/access-cert.pub"
```

Both resource lists must be empty. Keep sanitized receipts, not temporary keys.
