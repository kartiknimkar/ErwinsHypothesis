#!/usr/bin/env bash
# ================================================================
#  Erwin's Hypothesis - Mac launcher.  Run:  ./run.sh
#
#  Everything stays inside this folder:
#    runtime/   Python environment + libraries (made on first run)
#    projects/  your projects
#    exports/   exported graphs
#  Uses the Python already on this computer (3.10 or newer) if there
#  is one; otherwise downloads a private copy into runtime/python.
#  Options:  EH_PRIVATE_PYTHON=1  always use a private Python copy
#            EH_NO_UPDATE=1       don't check GitHub for updates at start
# ================================================================
# The whole script is wrapped in main() so bash reads it completely
# before running; an update can then safely replace this file.
main() {
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

RT="$ROOT/runtime"
VENV="$RT/venv"
PY="$VENV/bin/python"
UVEXE="$RT/uv/uv"
# Keep every download cache inside this folder, and ignore any
# libraries installed elsewhere on the computer.
export PIP_CACHE_DIR="$RT/cache/pip"
export UV_CACHE_DIR="$RT/cache/uv"
export UV_PYTHON_INSTALL_DIR="$RT/python"
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PYTHONNOUSERSITE=1
# Installers also use a temporary folder; keep that inside runtime/ too.
export TMPDIR="$RT/tmp"
mkdir -p "$RT" "$TMPDIR"

fail() {
  echo ""
  echo "Setup didn't finish. The messages above say why. If they mention"
  echo "connections or downloads, check your internet and try again."
  echo "(Only the first run needs internet.)"
  exit 1
}

suitable_python() {
  # macOS ships a /usr/bin/python3 placeholder that pops up an installer
  # dialog when the developer tools are missing; skip it in that case.
  local p="$1"
  command -v "$p" >/dev/null 2>&1 || return 1
  if [ "$(command -v "$p")" = "/usr/bin/python3" ] && [ "$(uname)" = "Darwin" ]; then
    xcode-select -p >/dev/null 2>&1 || return 1
  fi
  "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}

get_uv() {
  local arch os
  case "$(uname -m)" in
    arm64|aarch64) arch="aarch64" ;;
    *) arch="x86_64" ;;
  esac
  case "$(uname)" in
    Darwin) os="apple-darwin" ;;
    *) os="unknown-linux-gnu" ;;
  esac
  mkdir -p "$RT/uv"
  curl -fsSL "https://github.com/astral-sh/uv/releases/latest/download/uv-$arch-$os.tar.gz" \
    | tar -xz -C "$RT/uv" --strip-components=1
}

# --- Get the latest version from GitHub (if this folder is a clone) --
if [ "${EH_NO_UPDATE:-0}" != "1" ] && [ -d .git ] && command -v git >/dev/null 2>&1; then
  echo "Checking for updates..."
  if git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=10 pull --ff-only --quiet >/dev/null 2>&1; then
    echo "  Up to date."
  else
    echo "  Couldn't check for updates right now (offline?). Starting the current version."
  fi
fi

# --- 1. Reuse the existing environment if it still works ------------
if [ -x "$PY" ] && ! "$PY" -c 'import sys' >/dev/null 2>&1; then
  echo "The app's Python environment needs rebuilding (was Python updated or removed?)..."
  rm -rf "$VENV"
fi

if [ ! -x "$PY" ]; then
  SYS=""
  if [ "${EH_PRIVATE_PYTHON:-0}" != "1" ]; then
    for c in python3.13 python3.12 python3.11 python3.10 python3; do
      if suitable_python "$c"; then SYS="$c"; break; fi
    done
  fi
  # --- 2. Use a suitable Python already on this computer -------------
  if [ -n "$SYS" ] && "$SYS" -m venv "$VENV" >/dev/null 2>&1; then
    echo "Using the Python already installed on this computer ($("$SYS" --version))."
  else
    # --- 3. Otherwise, a private Python inside this folder -----------
    rm -rf "$VENV"
    echo "Setting up a private copy of Python inside this folder (first run only)..."
    [ -x "$UVEXE" ] || get_uv || fail
    "$UVEXE" venv --python 3.12 --python-preference only-managed "$VENV" || fail
    touch "$VENV/private.marker"
  fi
fi

# --- Install or update the libraries when requirements change -------
# --only-binary: use ready-made packages only, never try to compile anything
# (compiling needs developer tools most computers don't have).
install_libs() {
  if [ -f "$VENV/private.marker" ]; then
    "$UVEXE" pip install --only-binary :all: --python "$PY" -r backend/requirements.txt
  else
    "$PY" -m pip install --no-cache-dir --only-binary=:all: --progress-bar on -r backend/requirements.txt
  fi
}
if ! cmp -s backend/requirements.txt "$VENV/requirements.installed"; then
  echo ""
  echo "Installing the app's libraries (first run or after an update)."
  echo "This takes 1-2 minutes on a local disk. Progress is shown below."
  echo ""
  if ! install_libs; then
    [ -f "$VENV/private.marker" ] && fail
    echo ""
    echo "The Python on this computer can't use the app's ready-made libraries."
    echo "Switching to a private copy of Python inside this folder instead..."
    rm -rf "$VENV"
    [ -x "$UVEXE" ] || get_uv || fail
    "$UVEXE" venv --python 3.12 --python-preference only-managed "$VENV" || fail
    touch "$VENV/private.marker"
    install_libs || fail
  fi
  cp backend/requirements.txt "$VENV/requirements.installed"
fi

cd backend
exec "$PY" -m app.main
}

main "$@"
