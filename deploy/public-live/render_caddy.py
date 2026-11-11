#!/usr/bin/env python3
"""Render a candidate locally; never connects, deploys or infers host topology."""
import argparse
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--network-mode', required=True, help='Exact value read from the current Docker container')
parser.add_argument('--sha', required=True, help='Approved immutable merged source revision')
args = parser.parse_args()
if args.network_mode != 'host':
    parser.error('STOP: loopback-only Python requires Caddy host networking; no network change is authorized by this plan')
if not re.fullmatch(r'[a-f0-9]{40}', args.sha):
    parser.error('A full approved commit SHA is required')
print(Path(__file__).with_name('Caddyfile.template').read_text().replace('__STATIC_ROOT__', '/srv/releases/' + args.sha), end='')
