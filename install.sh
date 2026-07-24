#!/bin/bash
# RackForge — één commando na clone
# git clone https://github.com/stefpeerlings/rackforge.git rackforge-src && cd rackforge-src && bash install.sh
# (niet clonen naar "rackforge" zelf — dat botst met de API_DIR-default $HOME/rackforge)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec bash "$ROOT/scripts/restore-ubuntu.sh" "$@"