#!/bin/bash
# RackForge — één commando na clone
# git clone https://github.com/stefpeerlings/rackforge.git && cd rackforge && bash install.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec bash "$ROOT/scripts/restore-ubuntu.sh" "$@"