# apply_update.py
import zipfile
import json
import os
import subprocess
import shutil
import logging
import argparse
import sys
import stat
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

VERSION_FILE = 'version'

# === CONFIG ===
VENV_DIR = Path(".venv")
if os.name == 'nt':
    PIP_PATH = VENV_DIR / "Scripts" / "pip.exe"
    PYTHON_PATH = VENV_DIR / "Scripts" / "python.exe"
else:
    PIP_PATH = VENV_DIR / "bin" / "pip"
    PYTHON_PATH = VENV_DIR / "bin" / "python"

def version_to_tuple(version):
    try:
        return tuple(map(int, version.split('.')))
    except ValueError:
        logging.error(f"Invalid version format: {version}")
        raise


def force_remove(path):
    """Force remove file or directory, even if read-only."""
    def handle_remove_readonly(func, path, exc_info):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    path = os.path.abspath(path)
    if os.path.isfile(path):
        try:
            os.chmod(path, stat.S_IWRITE)
            os.remove(path)
            logging.info(f"Removed file: {path}")
        except Exception as e:
            logging.warning(f"Failed to remove file (retrying via parent): {e}")
            try:
                shutil.rmtree(os.path.dirname(path), onerror=handle_remove_readonly)
            except Exception as inner_e:
                logging.error(f"Failed to remove via parent: {inner_e}")
    elif os.path.isdir(path):
        shutil.rmtree(path, onerror=handle_remove_readonly)
        logging.info(f"Removed directory: {path}")


def apply_update(update_zip_path):
    """Apply update with hard replacement of all files."""
    if not os.path.exists(update_zip_path):
        raise FileNotFoundError(f"Update package not found: {update_zip_path}")

    try:
        with zipfile.ZipFile(update_zip_path, 'r') as zipf:
            metadata = json.loads(zipf.read('update_metadata.json'))
            to_version = metadata['to_version']
            from_version = metadata.get('from_version', 'unknown')
            logging.info(f"Applying HARD UPDATE: {from_version} → {to_version}")

            # --- PHASE 1: Delete files/dirs
            for file in metadata.get('deleted_files', []):
                file_path = (Path.cwd() / file).resolve()
                if file_path.exists():
                    force_remove(str(file_path))

            for dir_path in metadata.get('deleted_dirs', []):
                full_path = (Path.cwd() / dir_path).resolve()
                if full_path.exists():
                    force_remove(str(full_path))

            # --- PHASE 2: Extract all files (overwrite)
            for zip_info in zipf.infolist():
                # Skip metadata and snapshot
                if zip_info.filename in ['update_metadata.json', os.path.basename(snapshot_file)]:
                    continue

                target_path = (Path.cwd() / zip_info.filename).resolve()
                target_dir = target_path.parent

                if zip_info.filename.endswith('/'):
                    target_path.mkdir(parents=True, exist_ok=True)
                    continue

                if target_path.exists():
                    force_remove(str(target_path))

                target_dir.mkdir(parents=True, exist_ok=True)
                zipf.extract(zip_info, path=Path.cwd())

            # --- PHASE 3: Recreate added directories
            for dir_path in metadata.get('added_dirs', []):
                (Path.cwd() / dir_path).mkdir(parents=True, exist_ok=True)

            # --- PHASE 4: Update pip dependencies (ONE-BY-ONE, correct env)
            new_pip = metadata.get('new_pip', [])
            if new_pip:
                # Optional: save for debugging
                req_debug = 'temp_requirements_update.txt'
                with open(req_debug, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(new_pip))
                logging.info(f"Dependencies to install (logged in {req_debug}):")
                for pkg in new_pip:
                    logging.info(f"  → {pkg}")

                # Install one by one
                for package in new_pip:
                    package = package.strip()
                    if not package or package.startswith("#"):
                        continue

                    logging.info(f"Installing dependency: {package}")
                    try:
                        result = subprocess.run(
                            [str(PYTHON_PATH), '-m', 'pip', 'install', package],
                            capture_output=True,
                            text=True,
                            check=False  # Don't crash on failure
                        )
                        if result.returncode == 0:
                            logging.info(f"✅ Installed: {package}")
                        else:
                            logging.warning(f"⚠️ Failed to install: {package}")
                            logging.warning(f"stdout: {result.stdout}")
                            if "ERROR" in result.stderr or "exception" in result.stderr.lower():
                                logging.error(f"stderr: {result.stderr}")
                            # Optionally continue or raise
                    except Exception as e:
                        logging.error(f"Exception during install of '{package}': {e}")

                logging.info("Dependency installation phase completed.")

            # --- PHASE 5: Update version
            try:
                with open(VERSION_FILE, 'w', encoding='utf-8') as f:
                    f.write(f"{to_version}\n")
                logging.info(f"Version updated to {to_version}")
            except Exception as e:
                logging.error(f"Failed to write version file: {e}")
                raise

            logging.info(f"✅ HARD UPDATE SUCCESS: {to_version}")

    except Exception as e:
        logging.error(f"❌ HARD UPDATE FAILED: {e}")
        raise


def main():
    global snapshot_file
    parser = argparse.ArgumentParser(description="Apply update package with hard replace.")
    parser.add_argument('zip_file', nargs='?', help="Single update ZIP file")
    parser.add_argument('--many', nargs='*', help="Multiple update ZIPs")

    args = parser.parse_args()

    if not args.zip_file and not args.many:
        logging.error("No update file specified.")
        sys.exit(1)

    zip_files = args.many if args.many else [args.zip_file]

    for zip_path in zip_files:
        if not os.path.exists(zip_path):
            logging.error(f"File not found: {zip_path}")
            sys.exit(1)

    # Extract snapshot filename from first ZIP
    try:
        with zipfile.ZipFile(zip_files[0], 'r') as zf:
            snapshot_list = [f for f in zf.namelist() if f.startswith('snapshot_') and f.endswith('.json')]
            snapshot_file = snapshot_list[0] if snapshot_list else 'snapshot_.json'
    except Exception as e:
        logging.warning(f"Could not read ZIP list: {e}")
        snapshot_file = 'snapshot_.json'

    # Apply each update
    for zip_path in zip_files:
        logging.info(f"🚀 Applying update: {zip_path}")
        try:
            apply_update(zip_path)
        except Exception as e:
            logging.error(f"Update failed at {zip_path}: {e}")
            sys.exit(1)

    logging.info("🎉 All updates applied with HARD REPLACE.")
    filename = "./install_vk_server.sh.sh"

    # Add executable permissions for owner, group, and others
    os.chmod(filename, os.stat(filename).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f"{filename} is now executable.")
    sys.exit(0)


if __name__ == '__main__':
    main()
