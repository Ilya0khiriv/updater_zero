#!/bin/bash

# === RUN IN SCRIPT'S DIRECTORY ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || {
    echo "ERROR: Failed to enter script directory."
    exit 1
}

# === CONFIG ===
VENV_DIR=".venv"
VERSION_FILE="version.txt"
FIRST_RUN_FILE=".first_run"
SNAPSHOT_DIR="_snapshots"

PYTHON_VERSION="3.11.9"
PYTHON_MAJOR_MINOR="3.11"

UPDATER_URL="https://raw.githubusercontent.com/Ilya0khiriv/updater_zero/main/updater.py"
APPLY_URL="https://raw.githubusercontent.com/Ilya0khiriv/updater_zero/main/apply_update.py"
SNAPSHOT_URL="https://raw.githubusercontent.com/Ilya0khiriv/updater_zero/main/snapshooter.py"

FILES=("$UPDATER_URL" "$APPLY_URL" "$SNAPSHOT_URL")

REQUIREMENTS=(
    "requests"
    "psutil"
    "python-docx"
    "pillow"
    "pilmoji"
    "emoji==1.7.0"
    "pip-chill"
    "setuptools"
    "wheel"
    "pip"
)

# === COLORS ===
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_red()   { echo -e "${RED}[!] CHROME NOT INSTALLED — PLEASE INSTALL GOOGLE CHROME${NC}"; }

# === DETECT OS ===
detect_os() {
    case "$OSTYPE" in
        darwin*) OS="macos" ;;
        linux*)  OS="linux" ;;
        *) log_error "Unsupported OS: $OSTYPE"; exit 1 ;;
    esac
}

# === FIND PYTHON 3.11 WITH TKINTER ===
find_python() {
    local candidates=()

    if [ "$OS" = "macos" ]; then
        candidates=(
            "/usr/bin/python3"
            "/Library/Frameworks/Python.framework/Versions/$PYTHON_MAJOR_MINOR/bin/python3"
        )
    else
        candidates=(
            "/usr/bin/python$PYTHON_VERSION"
            "/usr/local/bin/python$PYTHON_VERSION"
            "/opt/python/$PYTHON_MAJOR_MINOR/bin/python"
            "python3"
        )
    fi

    for py in "${candidates[@]}"; do
        [ -z "$py" ] && continue

        if ! [[ "$py" == */* ]]; then
            py=$(command -v "$py" 2>/dev/null) || continue
        fi

        [ ! -x "$py" ] && continue

        if ! "$py" -c "import sys; exit(0 if sys.version_info[:2] == (3, 11) else 1)" &>/dev/null; then
            continue
        fi

        if ! "$py" -c "import tkinter" &>/dev/null; then
            log_warn "Python at $py lacks tkinter. Skipping."
            continue
        fi

        export PYTHON_CMD="$py"
        return 0
    done

    return 1
}

# === ENSURE PYTHON ON MACOS ===
ensure_python_macos() {
    if find_python; then
        log_info "Using existing Python: $PYTHON_CMD"
        return 0
    fi

    log_info "Installing Python $PYTHON_VERSION from python.org..."
    local pkg_url="https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-macos11.pkg"
    local pkg_name="/tmp/python-installer.pkg"

    if command -v curl &> /dev/null; then
        curl -fL -o "$pkg_name" "$pkg_url"
    else
        wget -O "$pkg_name" "$pkg_url"
    fi

    if [ ! -f "$pkg_name" ]; then
        log_error "Failed to download Python installer."
        exit 1
    fi

    log_info "Installing Python (admin password may be required)..."
    sudo installer -pkg "$pkg_name" -target / || {
        log_error "Python installation failed."
        rm -f "$pkg_name"
        exit 1
    }
    rm -f "$pkg_name"

    export PYTHON_CMD="/Library/Frameworks/Python.framework/Versions/$PYTHON_MAJOR_MINOR/bin/python3"
    if [ ! -x "$PYTHON_CMD" ]; then
        log_error "Python installed but not found at $PYTHON_CMD"
        exit 1
    fi

    if ! "$PYTHON_CMD" -c "import tkinter" &> /dev/null; then
        log_error "Python installed but lacks tkinter. Reinstall from python.org."
        exit 1
    fi

    log_info "Python $PYTHON_MAJOR_MINOR installed successfully."
}

# === ENSURE PYTHON + DEPS ON LINUX ===
ensure_python_linux() {
    if find_python; then
        log_info "Using existing Python: $PYTHON_CMD"
        return 0
    fi

    log_info "Python $PYTHON_MAJOR_MINOR not found. Installing required packages..."

    local missing_pkgs=()

    if command -v apt &> /dev/null; then
        for pkg in python3 python3-venv python3-pip python3-tk; do
            if ! dpkg -s "$pkg" >/dev/null 2>&1; then
                missing_pkgs+=("$pkg")
            fi
        done
        if [ ${#missing_pkgs[@]} -gt 0 ]; then
            sudo apt update && sudo apt install -y "${missing_pkgs[@]}"
        fi
        export PYTHON_CMD="python3"

    elif command -v dnf &> /dev/null; then
        for pkg in python3 python3-venv python3-pip; do
            if ! rpm -q "$pkg" >/dev/null 2>&1; then
                missing_pkgs+=("$pkg")
            fi
        done
        if [ ${#missing_pkgs[@]} -gt 0 ]; then
            sudo dnf install -y "${missing_pkgs[@]}"
        fi
        export PYTHON_CMD="python3"
    else
        log_error "Unsupported package manager. Install Python 3.11+ with tkinter manually."
        exit 1
    fi

    if ! "$PYTHON_CMD" -c "import tkinter" &> /dev/null; then
        log_error "tkinter is missing. On Debian/Ubuntu: sudo apt install python3-tk"
        exit 1
    fi

    log_info "Python setup complete using: $PYTHON_CMD"
}

# === SETUP PYTHON ===
setup_python() {
    if [ "$OS" = "macos" ]; then
        ensure_python_macos
    else
        ensure_python_linux
    fi
    log_info "Using Python: $PYTHON_CMD"
}

# === CREATE VENV IF MISSING ===
setup_venv() {
    if [ -d "$VENV_DIR" ]; then
        log_info "Virtual environment already exists. Skipping creation."
        return
    fi

    if [ ! -f "$FIRST_RUN_FILE" ]; then
        touch "$FIRST_RUN_FILE"
        log_info "Created: $FIRST_RUN_FILE"
    fi

    log_info "Creating virtual environment..."
    if ! "$PYTHON_CMD" -m venv "$VENV_DIR"; then
        log_error "Failed to create virtual environment."
        log_info "On Debian/Ubuntu: sudo apt install python3-venv"
        exit 1
    fi
    log_info "Virtual environment created."

    local python_bin="$VENV_DIR/bin/python"
    log_info "Installing core packages: pip, setuptools, wheel..."
    "$python_bin" -m ensurepip --upgrade || true
    "$python_bin" -m pip install --upgrade pip setuptools wheel || {
        log_error "Failed to install core Python packages."
        exit 1
    }
    log_info "Core packages installed."
}

# === CHECK IF PACKAGE IS INSTALLED IN VENV ===
is_pip_package_installed() {
    local pkg="$1"
    local import_name="$2"
    local python_bin="$VENV_DIR/bin/python"

    if "$python_bin" -c "import $import_name" &>/dev/null; then
        return 0
    fi

    if "$VENV_DIR/bin/pip" show "$pkg" &>/dev/null; then
        return 0
    fi

    return 1
}

# === INSTALL DEPENDENCIES ===
install_deps() {
    local pip_bin="$VENV_DIR/bin/pip"
    local python_bin="$VENV_DIR/bin/python"

    log_info "Upgrading pip..."
    "$python_bin" -m pip install --upgrade pip || log_warn "Could not upgrade pip."

    for pkg in "${REQUIREMENTS[@]}"; do
        local base_pkg="${pkg%%=*}"
        local import_name
        case "$base_pkg" in
            "python-docx") import_name="docx" ;;
            "pillow")      import_name="PIL" ;;
            "pip-chill")   import_name="pip_chill" ;;
            *)             import_name=$(echo "$base_pkg" | tr '-' '_') ;;
        esac

        if is_pip_package_installed "$base_pkg" "$import_name"; then
            log_info "✔ Already installed: $pkg"
        else
            log_info "Installing: $pkg"
            if "$pip_bin" install "$pkg"; then
                log_info "✔ Installed: $pkg"
            else
                log_error "Failed to install $pkg"
                exit 1
            fi
        fi
    done

    log_info "✅ All dependencies are installed and verified."
}

# === INSTALL SYSTEM BUILD DEPENDENCIES ===
install_build_deps() {
    if [ "$OS" = "macos" ]; then
        if ! command -v brew &> /dev/null; then
            log_info "Installing Homebrew..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            export PATH="/opt/homebrew/bin:$PATH"
        fi
        command -v ffmpeg || brew install ffmpeg
        command -v adb || brew install android-platform-tools
        return
    fi

    local missing_pkgs=()
    if command -v apt &> /dev/null; then
        local apt_pkgs=(
            libcairo2-dev libpango1.0-dev libgirepository1.0-dev
            pkg-config libffi-dev python3-dev meson ninja-build ffmpeg adb
        )
        for pkg in "${apt_pkgs[@]}"; do
            if ! dpkg -s "$pkg" >/dev/null 2>&1; then
                missing_pkgs+=("$pkg")
            fi
        done
        if [ ${#missing_pkgs[@]} -gt 0 ]; then
            sudo apt update && sudo apt install -y "${missing_pkgs[@]}"
        fi

    elif command -v dnf &> /dev/null; then
        local dnf_pkgs=(
            cairo-devel pango-devel glib2-devel gcc gcc-c++ python3-devel
            meson ninja-build ffmpeg android-tools
        )
        for pkg in "${dnf_pkgs[@]}"; do
            if ! rpm -q "$pkg" >/dev/null 2>&1; then
                missing_pkgs+=("$pkg")
            fi
        done
        if [ ${#missing_pkgs[@]} -gt 0 ]; then
            sudo dnf install -y "${missing_pkgs[@]}"
        fi
    else
        log_warn "Unsupported package manager. Install build deps manually."
    fi

    log_info "✅ Build dependencies, FFmpeg, and ADB are installed."
}

# === INSTALL GI (PyGObject) SYSTEM PACKAGE ONLY (LINUX ONLY) ===
install_gi_dependency() {
    if [ "$OS" != "linux" ]; then
        return 0
    fi

    log_info "Installing system 'gi' (PyGObject) dependencies..."

    local missing_pkgs=()
    local pkg_installed=false

    if command -v apt &> /dev/null; then
        for pkg in python3-gi python3-gi-cairo gir1.2-gtk-3.0 libgirepository1.0-dev; do
            if ! dpkg -s "$pkg" >/dev/null 2>&1; then
                missing_pkgs+=("$pkg")
            else
                pkg_installed=true
            fi
        done
        if [ ${#missing_pkgs[@]} -gt 0 ]; then
            sudo apt update && sudo apt install -y "${missing_pkgs[@]}"
            pkg_installed=true
        fi

    elif command -v dnf &> /dev/null; then
        for pkg in python3-gobject gtk3-devel gobject-introspection-devel; do
            if ! rpm -q "$pkg" >/dev/null 2>&1; then
                missing_pkgs+=("$pkg")
            else
                pkg_installed=true
            fi
        done
        if [ ${#missing_pkgs[@]} -gt 0 ]; then
            sudo dnf install -y "${missing_pkgs[@]}"
            pkg_installed=true
        fi

    elif command -v pacman &> /dev/null; then
        for pkg in python-gobject gtk3; do
            if ! pacman -Q "$pkg" &>/dev/null; then
                missing_pkgs+=("$pkg")
            else
                pkg_installed=true
            fi
        done
        if [ ${#missing_pkgs[@]} -gt 0 ]; then
            sudo pacman -S --noconfirm "${missing_pkgs[@]}"
            pkg_installed=true
        fi
    else
        log_warn "Unsupported package manager. Install 'python3-gi' manually."
        return
    fi

    if $pkg_installed; then
        log_info "✅ System 'gi' dependencies are installed."
    else
        log_info "💡 'gi' system packages were already installed."
    fi
}

# === FIX: SYMLINK gi INTO VENV (LINUX ONLY) ===
fix_gi_in_venv() {
    if [ "$OS" != "linux" ]; then
        return 0
    fi

    local python_version
    python_version="$("$VENV_DIR/bin/python" -c 'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}")')"
    local site_packages="$VENV_DIR/lib/$python_version/site-packages"

    log_info "Linking 'gi' and 'cairo' into virtual environment..."

    local system_dirs=(
        "/usr/lib/$python_version/site-packages"
        "/usr/lib/python3/dist-packages"
    )

    local found=false
    for sys_dir in "${system_dirs[@]}"; do
        if [ -d "$sys_dir/gi" ] && [ -d "$sys_dir/cairo" ]; then
            for mod in gi gi/types _gi _gi_cairo cairo; do
                if [ -e "$sys_dir/$mod" ] && [ ! -e "$site_packages/$mod" ]; then
                    ln -sf "$sys_dir/$mod" "$site_packages/$mod"
                    log_info "✔ Linked $mod"
                fi
            done
            found=true
            break
        fi
    done

    if $found; then
        log_info "✅ 'gi' is now accessible in the virtual environment."
    else
        log_error "❌ Could not find system 'gi' modules. Ensure python3-gi is installed."
    fi
}

# === VERIFY gi IMPORT WORKS IN VENV (LINUX ONLY) ===
verify_gi_import() {
    if [ "$OS" != "linux" ]; then
        return 0
    fi

    log_info "Testing 'import gi' in virtual environment..."
    if "$VENV_DIR/bin/python" -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk" &>/dev/null; then
        log_info "✅ 'gi' imported successfully."
    else
        log_error "❌ Failed to import 'gi'. Try reinstalling: sudo apt install python3-gi gir1.2-gtk-3.0"
        exit 1
    fi
}

# === VERIFY gi IMPORT WORKS IN VENV ===
verify_gi_import() {
    log_info "Testing 'import gi' in virtual environment..."
    if "$VENV_DIR/bin/python" -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk" &>/dev/null; then
        log_info "✅ 'gi' imported successfully."
    else
        log_error "❌ Failed to import 'gi'. Try reinstalling: sudo apt install python3-gi gir1.2-gtk-3.0"
        exit 1
    fi
}

# === DOWNLOAD SCRIPTS IF MISSING ===
download_scripts() {
    log_info "Downloading latest scripts (if missing)..."
    for url in "${FILES[@]}"; do
        local filename=$(basename "$url")
        if [ -f "$filename" ]; then
            log_info "✔ Already exists, skipping: $filename"
            continue
        fi
        rm -f "$filename"
        if command -v curl &> /dev/null; then
            curl -fsSL -o "$filename" "$url"
        else
            wget -qO "$filename" "$url"
        fi
        [ -f "$filename" ] && log_info "✔ Downloaded: $filename" || log_error "Failed: $url"
    done
}

# === CREATE VERSION FILE ===
create_version_file() {
    if [ ! -f "$VERSION_FILE" ]; then
        echo "0.0.0" > "$VERSION_FILE"
        log_info "Created: $VERSION_FILE"
    fi
}

# === CREATE SNAPSHOT ===
create_snapshot() {
    local version=$(cat "$VERSION_FILE" 2>/dev/null || echo "0.0.0")
    mkdir -p "$SNAPSHOT_DIR"
    log_info "Creating snapshot for version $version..."
    if [ -f "snapshooter.py" ]; then
        "$VENV_DIR/bin/python" "snapshooter.py" "$version"
        log_info "Snapshot saved to $SNAPSHOT_DIR/snapshot_${version}.json"
    else
        log_warn "snapshooter.py not found — skipping snapshot."
    fi
}

# === CHECK FOR GOOGLE CHROME ===
check_chrome() {
    if [ "$OS" = "macos" ] && [ -d "/Applications/Google Chrome.app" ]; then
        log_info "Google Chrome is installed. ✅"
    elif [ "$OS" = "linux" ] && command -v google-chrome &> /dev/null; then
        log_info "Google Chrome is installed. ✅"
    else
        echo ""
        log_red
        echo "   ➜ Please install Chrome: https://www.google.com/chrome/"
        echo ""
    fi
}

# === RUN UPDATER.PY ===
run_updater() {
    if [ ! -f "updater.py" ]; then
        log_error "updater.py not found!"
        exit 1
    fi
    log_info "Starting updater.py..."
    exec "$VENV_DIR/bin/python" "updater.py"
}

# === MAIN ===
# === MAIN ===
main() {
    detect_os
    log_info "Starting setup in: $(pwd)"

    setup_python
    setup_venv
    install_deps
    install_build_deps

    # Only run gi-related steps on Linux
    if [ "$OS" = "linux" ]; then
        install_gi_dependency
        fix_gi_in_venv
        verify_gi_import
    else
        log_info "Skipping gi (GTK) setup — not required on $OS."
    fi

    download_scripts
    create_version_file
    create_snapshot
    check_chrome

    log_info "Setup complete."
    run_updater
}

main