# AWS judge demo: owner-run deployment

**Hosting is prepared, not deployed. The requested Budget alerts were created and read back on 5 November 2026; no CrashCart compute instance exists.** The verified public demo remains [GitHub Pages](https://himanshu748.github.io/crashcart/). Keep that try-it link until the AWS HTTPS checks below pass. This Docker image serves the interactive recorded investigation, with outcomes computed during image build. It cannot initiate a payment, browser session or model call.

## Cost, boundaries and lifetime

Use **Lightsail Linux with public IPv4, 1 GB RAM, USD7/month base price**, including bundled disk and transfer. This is below the earlier USD10/month base infrastructure ceiling, without relying on free-trial eligibility. Taxes, excess traffic, optional snapshots and a new domain cost extra; use an existing domain and no snapshots, CDN, database or load balancer. Recheck the region's exact bundle before creation. [AWS pricing](https://aws.amazon.com/lightsail/pricing/), [bundle specifications](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.html).

Keep the instance, attached IP, DNS and certificate volumes through **15 December 2026**, including judging's 21:30 IST end. Do not remove them before **16 December 00:00 IST**. Restart policy handles process/host restarts, not every outage. Check the public URL daily. No automatic deletion is installed and future uptime is not yet verified.

The requested USD20/USD50 alerts watch **total monthly account cost**, including other projects. Alerts are delayed notifications, not spending caps or authorization to spend USD50. The owner runs the following AWS mutations. No provider credentials belong on this server. TLS and SSH necessarily generate private host keys; “no secrets” means no application/provider/AWS credentials, not zero cryptographic keys.

## 1. Owner inputs and local prerequisites

Run on your Mac from a clean public clone containing these files. You need AWS CLI v2 authenticated to the intended account, Python 3.11+, an existing domain with DNS access, and an RSA SSH key. Replace every uppercase placeholder. Never upload the private working archive or `.env`.

```sh
set -eu
export AWS_REGION=us-east-1
export AWS_PAGER=''
export CC_INSTANCE=crashcart-judge-2026
export CC_STATIC_IP=crashcart-judge-ip-2026
export CC_KEY_NAME=crashcart-judge-2026
export CC_BUDGET_EMAIL='YOUR_ALERT_EMAIL'
export JUDGE_DOMAIN='demo.YOUR_EXISTING_DOMAIN'
export ACME_EMAIL='YOUR_CERTIFICATE_EMAIL'
export CC_ADMIN_CIDR='YOUR_CURRENT_PUBLIC_IPV4/32'
export CC_SSH_KEY="$HOME/.ssh/crashcart-judge-2026"
export CC_RELEASE=$(git rev-parse HEAD)
date -u
aws sts get-caller-identity
```

`CC_RELEASE` must be a reviewed, pushed commit containing this plan. If CLI login is missing, use your AWS console/SSO; do not create/share root access keys. Create the dedicated local key only if it does not exist; choose a passphrase when prompted:

```sh
test ! -e "$CC_SSH_KEY" && ssh-keygen -t rsa -b 3072 -f "$CC_SSH_KEY" -C crashcart-judge
```

## 2. Create and read back Budget alerts

**Current maintainer account:** this budget already exists. Skip the `create-budget` command and use the readback commands; do not replace it. [Verified configuration](../evidence/runs/submission-ready/budget-verified-v62.json). Both recipient matches passed, but actual email delivery was not tested. The creation command below is for a different account where the named budget is absent.

One monthly USD50 cost budget has absolute ACTUAL notifications **above USD20** and **above USD50**, to your selected email. The Python helper only writes JSON. Store requests outside the repo. [AWS Budget CLI](https://docs.aws.amazon.com/cli/latest/reference/budgets/create-budget.html).

```sh
export CC_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export CC_BUDGET_DIR=$(mktemp -d)
python3 deploy/judge/budget-files.py --email "$CC_BUDGET_EMAIL" --output "$CC_BUDGET_DIR"
date -u
aws budgets create-budget --region us-east-1 --account-id "$CC_ACCOUNT_ID" \
  --budget "file://$CC_BUDGET_DIR/budget.json" \
  --notifications-with-subscribers "file://$CC_BUDGET_DIR/notifications.json"
aws budgets describe-budget --region us-east-1 --account-id "$CC_ACCOUNT_ID" \
  --budget-name CrashCart-account-monthly-alerts
aws budgets describe-notifications-for-budget --region us-east-1 \
  --account-id "$CC_ACCOUNT_ID" --budget-name CrashCart-account-monthly-alerts
for threshold in 20 50; do
  aws budgets describe-subscribers-for-notification --region us-east-1 \
    --account-id "$CC_ACCOUNT_ID" --budget-name CrashCart-account-monthly-alerts \
    --notification "NotificationType=ACTUAL,ComparisonOperator=GREATER_THAN,Threshold=$threshold,ThresholdType=ABSOLUTE_VALUE"
done
```

Confirm both thresholds and recipient in readback and Billing → Budgets. If the name already exists, inspect it instead of deleting/replacing it. Resolve Billing permissions in the console. API readback proves configuration, not email delivery.

## 3. Select and create one Lightsail instance

Query current IDs. The selector stops if the expected active USD7 Linux 1 GB plan is absent/ambiguous. Do not silently choose a higher price.

```sh
aws lightsail get-bundles --region "$AWS_REGION" --no-include-inactive > "$CC_BUDGET_DIR/bundles.json"
export CC_BUNDLE_ID=$(python3 - "$CC_BUDGET_DIR/bundles.json" <<'PY'
import json, sys
rows = [x for x in json.load(open(sys.argv[1]))['bundles']
        if x.get('isActive') and x.get('price') == 7 and x.get('ramSizeInGb') == 1
        and 'LINUX_UNIX' in x.get('supportedPlatforms', [])]
assert len(rows) == 1, 'Inspect available plans; do not increase the price automatically'
print(rows[0]['bundleId'])
PY
)
test -n "$CC_BUNDLE_ID"
aws lightsail get-blueprints --region "$AWS_REGION" --no-include-inactive \
  --query "blueprints[?blueprintId=='ubuntu_24_04'].[blueprintId,isActive]" --output table
aws lightsail get-regions --include-availability-zones \
  --query "regions[?name=='us-east-1'].availabilityZones" --output table
```

Continue only if `ubuntu_24_04` is active and `us-east-1a` available. Otherwise explicitly select a supported Ubuntu LTS/zone first. Creation starts paid usage. Import only the public RSA key:

```sh
aws lightsail import-key-pair --region "$AWS_REGION" --key-pair-name "$CC_KEY_NAME" \
  --public-key-base64 "$(base64 < "$CC_SSH_KEY.pub" | tr -d '\n')"
aws lightsail create-instances --region "$AWS_REGION" --instance-names "$CC_INSTANCE" \
  --availability-zone us-east-1a --blueprint-id ubuntu_24_04 --bundle-id "$CC_BUNDLE_ID" \
  --key-pair-name "$CC_KEY_NAME" --ip-address-type ipv4 \
  --tags key=Project,value=CrashCart key=KeepThrough,value=2026-12-15
aws lightsail get-instance --region "$AWS_REGION" --instance-name "$CC_INSTANCE" \
  --query 'instance.[state.name,bundleId,blueprintId]' --output table
```

Wait until state is `running`; read back instead of repeating creation. Allocate/attach a static IP immediately; unattached static IPs can cost extra. Replace the firewall with public HTTP/HTTPS and SSH restricted to your current IP. [AWS firewall command](https://docs.aws.amazon.com/cli/latest/reference/lightsail/put-instance-public-ports.html).

```sh
aws lightsail allocate-static-ip --region "$AWS_REGION" --static-ip-name "$CC_STATIC_IP"
aws lightsail attach-static-ip --region "$AWS_REGION" --static-ip-name "$CC_STATIC_IP" --instance-name "$CC_INSTANCE"
aws lightsail put-instance-public-ports --region "$AWS_REGION" --instance-name "$CC_INSTANCE" \
  --port-infos "[{\"fromPort\":22,\"toPort\":22,\"protocol\":\"tcp\",\"cidrs\":[\"$CC_ADMIN_CIDR\"]},{\"fromPort\":80,\"toPort\":80,\"protocol\":\"tcp\",\"cidrs\":[\"0.0.0.0/0\"]},{\"fromPort\":443,\"toPort\":443,\"protocol\":\"tcp\",\"cidrs\":[\"0.0.0.0/0\"]}]"
export CC_PUBLIC_IP=$(aws lightsail get-static-ip --region "$AWS_REGION" --static-ip-name "$CC_STATIC_IP" --query staticIp.ipAddress --output text)
aws lightsail get-instance-port-states --region "$AWS_REGION" --instance-name "$CC_INSTANCE"
printf 'DNS A record: %s -> %s\nReviewed release: %s\n' "$JUDGE_DOMAIN" "$CC_PUBLIC_IP" "$CC_RELEASE"
```

Create that DNS A record in your existing provider, DNS-only if proxying is offered. Remove stale AAAA records for this hostname unless IPv6 is deliberately configured. Do not purchase a domain/hosted zone. Verify public DNS resolves correctly before HTTPS startup.

## 4. Install Docker and start the recorded review

Connect with `ssh -i "$CC_SSH_KEY" "ubuntu@$CC_PUBLIC_IP"`. Verify the host fingerprint through Lightsail's console; do not disable host checking. These commands run **on the new Ubuntu server**. They use [Docker's official Ubuntu package repository](https://docs.docker.com/engine/install/ubuntu/), without a remote shell installer.

```sh
set -eu
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
printf 'Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: %s\nComponents: stable\nArchitectures: %s\nSigned-By: /etc/apt/keyrings/docker.asc\n' \
  "$VERSION_CODENAME" "$(dpkg --print-architecture)" | sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
git clone https://github.com/himanshu748/crashcart.git crashcart-judge
cd crashcart-judge
export CC_RELEASE='PASTE_REVIEWED_FULL_COMMIT_FROM_STEP_1'
git checkout --detach "$CC_RELEASE"
export JUDGE_DOMAIN='demo.YOUR_EXISTING_DOMAIN'
export ACME_EMAIL='YOUR_CERTIFICATE_EMAIL'
sudo env JUDGE_DOMAIN="$JUDGE_DOMAIN" ACME_EMAIL="$ACME_EMAIL" \
  docker compose -f deploy/judge/compose.yaml config --quiet
sudo env JUDGE_DOMAIN="$JUDGE_DOMAIN" ACME_EMAIL="$ACME_EMAIL" \
  docker compose -f deploy/judge/compose.yaml build --pull
sudo env JUDGE_DOMAIN="$JUDGE_DOMAIN" ACME_EMAIL="$ACME_EMAIL" \
  docker compose -f deploy/judge/compose.yaml run --rm --no-deps judge \
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo env JUDGE_DOMAIN="$JUDGE_DOMAIN" ACME_EMAIL="$ACME_EMAIL" \
  docker compose -f deploy/judge/compose.yaml up -d --no-build
```

The image's final stage contains Caddy and public exported assets, no Python application/live adapter. Only hostname and contact email are passed in. Caddy stores certificate private keys in its persistent `caddy_data` volume. Keep it private and persistent; do not run `down -v`. [Automatic HTTPS](https://caddyserver.com/docs/automatic-https).

Record `git rev-parse HEAD`, `sudo docker image inspect crashcart-judge:reviewed --format '{{.Id}}'` and build output. Base image tags resolve at build time; record the resulting image ID and don't rebuild during judging without reverification.

## 5. Verify the actual HTTPS target before sharing it

From your Mac:

```sh
curl --fail --silent --show-error -I "https://$JUDGE_DOMAIN/"
curl --fail --silent --show-error "https://$JUDGE_DOMAIN/data.json" -o "$CC_BUDGET_DIR/hosted-data.json"
python3 - "$CC_BUDGET_DIR/hosted-data.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
assert d['mode'] == 'RECORDED_REPLAY' and d['network_calls'] == 0
assert d['computed_when'] == 'site build' and d['fresh_execution'] is False
for variant, expected in [('defective', ('FAIL', 'paid_without_ticket', 0)),
                          ('healthy', ('PASS', 'ticket_delivered_once_on_time', 1))]:
    r = d['cases'][variant]['receipt']
    actual = (r['verdict'], r['signature'], r['ticket_count'])
    assert actual == expected, (variant, actual)
    print(variant, *actual)
PY
curl --silent --output /dev/null --write-out '%{http_code}\n' -X POST "https://$JUDGE_DOMAIN/"
curl --silent --output /dev/null --write-out '%{http_code}\n' "https://$JUDGE_DOMAIN/.env"
curl --fail --silent --show-error "https://$JUDGE_DOMAIN/downloads/replay.zip" -o "$CC_BUDGET_DIR/replay.zip"
python3 -m zipfile -t "$CC_BUDGET_DIR/replay.zip"
```

Expected: trusted HTTPS 200; defective FAIL; healthy PASS; POST 405; `.env` 404; ZIP integrity passes. In the browser exercise landing → walkthrough → defective evidence → healthy comparison → download; check keyboard and phone-width layout. Keep the recorded-replay label visible. Save sanitized receipts, source commit, image ID and screenshots. Only then replace the try-it URL. API setup is not uptime proof; check daily through judging. Keep GitHub Pages as fallback.

## What is verified here, and what is still owner-run

The original 4 November attempt had Docker CLI but no running daemon or discovered Compose plugin. On 5 November, the default local Colima environment started, standalone `docker-compose` 5.6.1 validated the configuration, and installing Buildx enabled an actual image build. [Local container evidence](../evidence/runs/submission-ready/container-verified-v62.json) records Caddy validation, ARM64 loopback HTTP checks, actual browser interactions and executable ZIP replay. No container/deployment source changed. Public TLS and actual AWS hosting remain unverified. Container build, Caddy validation, AWS compute provisioning and public TLS were unverified in the original 4 November preparation. Budget creation and configuration readback subsequently passed on 5 November; email delivery remains unverified. [Preparation evidence](../deploy/judge/preparation-verification.json) records the actual minimal-context Python export: defective FAIL, healthy PASS, zero provider calls. The first export failed because the migration was omitted; the corrected context passed on the second attempt. Budget JSON thresholds and invalid-email rejection passed, as did syntax checks of all nine documented shell blocks. These do not establish container or AWS runtime behavior. The owner supplies authenticated AWS access, alert email, existing domain/DNS and SSH administration, and runs the provisioning/validation above. No application credentials or new payment are required. Stop if a step fails twice; preserve the errors rather than relaxing checks.

## Cleanup only after judging

On/after 16 December 2026, once access is no longer needed, remove the DNS record and run on your Mac. This permanently deletes this dedicated instance/data. Stopping alone does not eliminate its charge; keep the budget alerts unless intentionally no longer wanted.

```sh
set -eu
aws lightsail delete-instance --region "$AWS_REGION" --instance-name "$CC_INSTANCE"
aws lightsail get-static-ip --region "$AWS_REGION" --static-ip-name "$CC_STATIC_IP"
# Once readback shows the address is detached:
aws lightsail release-static-ip --region "$AWS_REGION" --static-ip-name "$CC_STATIC_IP"
aws lightsail get-instances --region "$AWS_REGION" --query "instances[?name=='$CC_INSTANCE'].name"
aws lightsail get-static-ips --region "$AWS_REGION" --query "staticIps[?name=='$CC_STATIC_IP'].name"
```

Both final lists must be empty. Do not leave an unattached static IP allocated.
