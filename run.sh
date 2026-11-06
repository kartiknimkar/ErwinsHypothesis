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
#  To always use a private copy:  EH_PRIVATE_PYTHON=1 ./run.sh
# ================================================================
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
mkdir -p "$RT"

fail() {
  echo ""
  echo "Setup didn't finish. Check your internet connection and try again."
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
    "$UVEXE" venv --quiet --python 3.12 --python-preference only-managed "$VENV" || fail
  fi
fi

# --- Install or update the libraries when requirements change -------
if ! cmp -s backend/requirements.txt "$VENV/requirements.installed"; then
  echo "Installing the app's libraries (first run or update; about a minute)..."
  if [ -x "$UVEXE" ]; then
    "$UVEXE" pip install --quiet --python "$PY" -r backend/requirements.txt || fail
  else
    "$PY" -m pip install --quiet --no-cache-dir -r backend/requirements.txt || fail
  fi
  cp backend/requirements.txt "$VENV/requirements.installed"
fi

cd backend
exec "$PY" -m app.main
