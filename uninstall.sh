#!/bin/sh
# Remove Pathfinder (keeps your results in your home folder › Pathfinder Results and keeps uv).
#   curl -LsSf https://raw.githubusercontent.com/Zaf4/Pathfinder/2.1.0/uninstall.sh | sh
export PATH="$HOME/.local/bin:$PATH"
command -v uv >/dev/null 2>&1 && uv tool uninstall jsl-pathfinder >/dev/null 2>&1
rm -rf "$HOME/Applications/Pathfinder.app" "$HOME/.local/share/applications/pathfinder.desktop"
echo "Pathfinder has been removed. Your results in your home folder › Pathfinder Results were kept."
