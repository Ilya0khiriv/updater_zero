#!/bin/bash
set -e

# === COLORS ===
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_verbose() { echo -e "[VERBOSE] $1"; }

# === PREVENT PIPED EXECUTION ===
if [[ "$0" == "/dev/stdin" || "$0" == "bash" || "$0" == "-bash" ]]; then
    log_error "This script must be saved to a file and run directly."
    log_error "Do NOT use: curl ... | bash"
    exit 1
fi

# === DETECT OS ===
case "$OSTYPE" in
    linux*)   OS="linux" ;;
    darwin*)  OS="macos" ;;
    *)        log_error "Unsupported OS: $OSTYPE"; exit 1 ;;
esac

# === SET PATHS ===
if [[ "$OS" == "macos" ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/VK Uploader"
    APP_PATH="$HOME/Applications/VK Uploader.app"
elif [[ "$OS" == "linux" ]]; then
    CONFIG_DIR="$HOME/.local/share/VK Uploader"
    BIN_DIR="$HOME/.local/bin"
    APP_PATH="$BIN_DIR/vk-uploader"
    DESKTOP_FILE="$HOME/.local/share/applications/vk-uploader.desktop"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
TARGET_SCRIPT="$CONFIG_DIR/$SCRIPT_NAME"
BUILT_MARKER="$CONFIG_DIR/built"

log_verbose "Detected OS: $OS"
log_verbose "Config directory: $CONFIG_DIR"

# === RUNNING FROM INSTALLED LOCATION ===
if [[ "$SCRIPT_DIR" == "$CONFIG_DIR" ]]; then
    UPDATE_PY="$CONFIG_DIR/update.py"
    if [[ ! -f "$UPDATE_PY" ]]; then
        log_info "Downloading update.py..."
        curl -fsSL -o "$UPDATE_PY" \
            "https://raw.githubusercontent.com/Ilya0khiriv/updater_zero/main/pyqt5_vk_uploader_folder/update.py?$RANDOM"
    fi
    log_verbose "Running from installed location."

    if [[ -f "$BUILT_MARKER" ]]; then
        log_verbose "Runtime mode: launching app."

        VENV="$CONFIG_DIR/.venv"
        if [[ ! -d "$VENV" ]]; then
            log_error "Virtual environment missing."
            exit 1
        fi

        # Ensure deps
        MISSING=()
        for pkg in PyQt5 requests; do
            if ! "$VENV/bin/python" -c "import $pkg" &>/dev/null; then
                MISSING+=("$pkg")
            fi
        done
        if [[ ${#MISSING[@]} -gt 0 ]]; then
            log_info "Installing: ${MISSING[*]}"
            "$VENV/bin/pip" install --quiet --upgrade pip
            "$VENV/bin/pip" install --quiet "${MISSING[@]}"
        fi

        # Ensure app code
        if [[ ! -d "$CONFIG_DIR/pyqt5_ui" ]]; then
            UPDATE_PY="$CONFIG_DIR/update.py"
            log_info "Running updater..."
            "$VENV/bin/python" "$UPDATE_PY"
        fi

        if [[ -d "$CONFIG_DIR/pyqt5_ui" ]] && [[ -f "$CONFIG_DIR/pyqt5_ui/main.py" ]]; then
            log_info "Launching main application..."
            exec "$VENV/bin/python" -m pyqt5_ui.main
        else
            log_error "pyqt5_ui/main.py not found after update."
            exit 1
        fi
    fi

    # === FIRST-TIME BUILD ===
    log_info "First-time build: creating launcher..."

    # Create venv if missing
    VENV="$CONFIG_DIR/.venv"
    if [[ ! -d "$VENV" ]]; then
        PY311=""
        for cand in python3.11 python3; do
            if command -v "$cand" >/dev/null 2>&1; then
                if "$cand" -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
                    PY311="$cand"
                    break
                fi
            fi
        done
        if [[ -z "$PY311" ]]; then
            log_error "Python 3.11+ not found."
            exit 1
        fi
        "$PY311" -m venv "$VENV"
    fi

    "$VENV/bin/pip" install --quiet --upgrade pip
    "$VENV/bin/pip" install --quiet pyinstaller

    # launcher_stub.py
    cat > "$CONFIG_DIR/launcher_stub.py" << EOF
import os
import sys
CONFIG_DIR = "$CONFIG_DIR"
init_sh = os.path.join(CONFIG_DIR, "init.sh")
if not os.path.isfile(init_sh):
    sys.exit("FATAL: init.sh not found")
os.chdir(CONFIG_DIR)
os.execv("/bin/bash", ["/bin/bash", init_sh])
EOF

    # macOS icon
    ICON_ARG=""
    if [[ "$OS" == "macos" ]]; then
        ICON_PATH="$CONFIG_DIR/AppIcon.icns"
        if [[ ! -f "$ICON_PATH" ]]; then
            PNG="$CONFIG_DIR/vk-logo.png"
            if curl -fsSL -o "$PNG" \
                "https://raw.githubusercontent.com/Ilya0khiriv/updater_zero/main/pyqt5_vk_uploader_folder/vk-logo.png"; then
                ICONSET="$CONFIG_DIR/AppIcon.iconset"
                mkdir -p "$ICONSET"
                sips -z 512 512 "$PNG" --out "$ICONSET/icon_512x512.png" >/dev/null
                sips -z 1024 1024 "$PNG" --out "$ICONSET/icon_512x512@2x.png" >/dev/null
                iconutil -c icns -o "$ICON_PATH" "$ICONSET"
                rm -rf "$ICONSET" "$PNG"
            fi
        fi
        if [[ -f "$ICON_PATH" ]]; then
            ICON_ARG="--icon=$ICON_PATH"
        fi
    fi

    # Build with PyInstaller (ONEFILE!)
    cd "$CONFIG_DIR"
    PYINST_CMD=("$VENV/bin/pyinstaller")
    PYINST_CMD+=("--clean" "--noconfirm" "--windowed")
    PYINST_CMD+=("--onefile")  # ← CRITICAL: single executable
    if [[ "$OS" == "macos" ]]; then
        PYINST_CMD+=("--name=VK Uploader")
        PYINST_CMD+=("--osx-bundle-identifier=com.vk.uploader")
    else
        PYINST_CMD+=("--name=vk-uploader")
    fi
    if [[ -n "$ICON_ARG" ]]; then
        PYINST_CMD+=("$ICON_ARG")
    fi
    PYINST_CMD+=("launcher_stub.py")

    "${PYINST_CMD[@]}"

    # Install
    if [[ "$OS" == "macos" ]]; then
        if [[ -d "$APP_PATH" ]]; then rm -rf "$APP_PATH"; fi
        mv "dist/VK Uploader.app" "$APP_PATH"
    elif [[ "$OS" == "linux" ]]; then
        mkdir -p "$BIN_DIR"
        if [[ -f "$APP_PATH" ]]; then rm -f "$APP_PATH"; fi
        mv "dist/vk-uploader" "$APP_PATH"
        chmod +x "$APP_PATH"

        # Icon
        ICON_PNG="$CONFIG_DIR/vk-logo.png"
        if [[ ! -f "$ICON_PNG" ]]; then
            curl -fsSL -o "$ICON_PNG" \
                "https://raw.githubusercontent.com/Ilya0khiriv/updater_zero/main/pyqt5_vk_uploader_folder/vk-logo.png"
        fi

        # .desktop file
        mkdir -p "$HOME/.local/share/applications"
        cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=VK Uploader
Exec=$APP_PATH
Terminal=false
Type=Application
Categories=Network;
StartupNotify=true
Icon=$ICON_PNG
EOF

        chmod +x "$DESKTOP_FILE"
        if command -v update-desktop-database >/dev/null 2>&1; then
            update-desktop-database "${DESKTOP_FILE%/*}" >/dev/null 2>&1 || true
        fi
    fi

    # Cleanup
    rm -rf build/ dist/ *.spec launcher_stub.py
    "$VENV/bin/pip" uninstall --quiet -y pyinstaller
    touch "$BUILT_MARKER"

    if [[ "$OS" == "macos" ]]; then
        log_info "✅ App built at: ~/Applications/VK Uploader.app"
    else
        log_info "✅ App installed to: $APP_PATH"
        log_info "   Desktop entry: $DESKTOP_FILE"
    fi
    exit 0
fi

# === FIRST RUN: INSTALL TO CONFIG DIR ===
log_info "🚀 First run. Installing to config directory..."

mkdir -p "$CONFIG_DIR"
cp "$SCRIPT_DIR/$SCRIPT_NAME" "$TARGET_SCRIPT"
chmod +x "$TARGET_SCRIPT"

# Create venv
PY311=""
for cand in python3.11 python3; do
    if command -v "$cand" >/dev/null 2>&1; then
        if "$cand" -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
            PY311="$cand"
            break
        fi
    fi
done
if [[ -z "$PY311" ]]; then
    log_error "Python 3.11+ not found."
    exit 1
fi

"$PY311" -m venv "$CONFIG_DIR/.venv"

log_info "Relaunching from installed location..."
exec "$TARGET_SCRIPT"
