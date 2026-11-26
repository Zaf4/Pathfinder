#!/bin/sh
# Pathfinder installer for macOS and Linux.
#
#   curl -LsSf https://raw.githubusercontent.com/Zaf4/Pathfinder/master/install.sh | sh
#
# Installs uv (a small Python manager) and Pathfinder into your home folder.
# No administrator password, Homebrew, conda, git or Xcode needed. Run it again to update.
set -eu

REPO="https://github.com/Zaf4/Pathfinder"
BRANCH="${PATHFINDER_BRANCH:-master}"
# A zip download on purpose: a git URL would need git, and on a stock Mac merely calling git
# pops up "install the command line developer tools" and the install fails.
SOURCE="${PATHFINDER_SOURCE:-jsl-pathfinder @ ${REPO}/archive/refs/heads/${BRANCH}.zip}"
PY="3.13"

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
step() { printf '\n\033[1;36m==>\033[0m \033[1m%s\033[0m\n' "$1"; }
fail() { printf '\n\033[1;31mSomething went wrong:\033[0m %s\n' "$1" >&2; exit 1; }

bold "Installing Pathfinder…"

export PATH="$HOME/.local/bin:$PATH"

step "1/3  Getting uv (Python manager)"
if command -v uv >/dev/null 2>&1; then
  echo "uv is already installed."
else
  curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null || fail "could not download uv. Check your internet connection."
fi
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
[ -x "$UV" ] || fail "uv was not installed."

step "2/3  Installing Pathfinder (first time takes a minute)"
# --managed-python: always uv's own Python. A python.org "framework" Python on the Mac would
# otherwise be reused, and it relaunches itself as "Python.app" (wrong Dock icon and name).
"$UV" tool install --force --refresh-package jsl-pathfinder --managed-python --python "$PY" "$SOURCE" || fail "installing Pathfinder failed."
BIN="$("$UV" tool dir --bin)/pathfinder"
[ -x "$BIN" ] || fail "the pathfinder program is missing after install."

step "3/3  Adding Pathfinder to your Applications"
case "$(uname -s)" in
Darwin)
  APP="$HOME/Applications/Pathfinder.app"
  rm -rf "$APP"
  mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
  # The launcher is a script, and macOS may start script-based apps under Rosetta (Intel
  # emulation) on Apple Silicon. The installed Python and libraries are native arm64, so
  # they'd fail to load and the app would quietly not open. Always run natively.
  cat > "$APP/Contents/MacOS/Pathfinder" <<EOF
#!/bin/sh
if [ "\$(/usr/sbin/sysctl -n hw.optional.arm64 2>/dev/null)" = "1" ]; then
  exec /usr/bin/arch -arm64 "$BIN" "\$@"
fi
exec "$BIN" "\$@"
EOF
  chmod +x "$APP/Contents/MacOS/Pathfinder"
  ICON_SRC="$("$UV" tool dir)/jsl-pathfinder"
  ICNS="$(find "$ICON_SRC" -name AppIcon.icns -print -quit 2>/dev/null || true)"
  if [ -n "$ICNS" ]; then
    cp "$ICNS" "$APP/Contents/Resources/AppIcon.icns"
  else
    curl -fsSL "https://raw.githubusercontent.com/Zaf4/Pathfinder/${BRANCH}/src/pathfinder/gui/assets/AppIcon.icns" \
      -o "$APP/Contents/Resources/AppIcon.icns" 2>/dev/null || true
  fi
  VERSION="$("$UV" tool list 2>/dev/null | awk '/^jsl-pathfinder/ {sub(/^v/, "", $2); print $2}')"
  cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Pathfinder</string>
  <key>CFBundleDisplayName</key><string>Pathfinder</string>
  <key>CFBundleIdentifier</key><string>io.github.zaf4.pathfinder</string>
  <key>CFBundleExecutable</key><string>Pathfinder</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>${VERSION:-2.0}</string>
  <key>CFBundleVersion</key><string>${VERSION:-2.0}</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>LSArchitecturePriority</key><array><string>arm64</string><string>x86_64</string></array>
  <key>LSRequiresNativeExecution</key><true/>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSRequiresAquaSystemAppearance</key><false/>
</dict>
</plist>
EOF
  # Built on this Mac (nothing downloaded is quarantined), but make sure Gatekeeper never asks:
  # clear any quarantine flag and give the bundle a local ad-hoc signature.
  xattr -cr "$APP" 2>/dev/null || true
  codesign --force --sign - "$APP" >/dev/null 2>&1 || true
  # refresh Finder/Launchpad so the icon shows up right away
  touch "$APP"
  LSREG=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
  [ -x "$LSREG" ] && "$LSREG" -f "$APP" >/dev/null 2>&1 || true
  WHERE="your Applications folder, Launchpad and Spotlight"
  ;;
Linux)
  DESK="$HOME/.local/share/applications"
  mkdir -p "$DESK"
  ICON="$(find "$("$UV" tool dir)/jsl-pathfinder" -name icon_256.png -print -quit 2>/dev/null || true)"
  cat > "$DESK/pathfinder.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Pathfinder
Comment=Morris Water Maze search strategy analysis
Exec=$BIN %F
Icon=${ICON:-pathfinder}
Terminal=false
Categories=Science;Education;
EOF
  WHERE="your applications menu"
  ;;
*)
  WHERE="the terminal (type: pathfinder)"
  ;;
esac

printf '\n\033[1;32m✓ Pathfinder is installed.\033[0m\n'
echo "  Open it from $WHERE."
echo "  Your results will be saved in the \"Pathfinder Results\" folder in your home folder."
echo "  To update later, run this same command again (or use Help → Check for Updates)."

if [ "$(uname -s)" = "Darwin" ] && [ -z "${PATHFINDER_NO_OPEN:-}" ]; then
  open "$APP" 2>/dev/null || true
fi
