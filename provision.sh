#!/usr/bin/env bash
set -euo pipefail

yum install -y python3
pip3 install /tmp/ebs-pin
/usr/local/bin/ebs-pin --help
