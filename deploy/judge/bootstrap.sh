#!/bin/sh
# Public judge-only host prerequisites. No application credentials belong here.
set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y docker.io docker-compose-v2 docker-buildx ca-certificates unattended-upgrades
systemctl enable --now docker
docker compose version
docker buildx version
# A bounded on-disk build buffer for the 1 GB instance; included root disk only.
if [ ! -e /swapfile ]; then
    fallocate -l 1G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    printf '%s\n' '/swapfile none swap sw 0 0' >> /etc/fstab
fi
# Fail closed if a previous interrupted setup left an inactive swap file.
swapon --noheadings --show=NAME | grep -Fx /swapfile
