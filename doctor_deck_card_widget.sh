#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
./acceptance_deck_card_widget.sh
[[ -f requirements.txt ]] && echo "PASS: requirements.txt exists"
[[ -f data/templates/default_episode_template.buttstore ]] && echo "PASS: default template exists"
[[ -f data/emoji_presets/default_presets.emoji ]] && echo "PASS: emoji presets exist"
