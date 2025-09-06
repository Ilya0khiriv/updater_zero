# snapshooter.py
import os
import hashlib
import zipfile
import json
import subprocess
from pathlib import Path
import argparse
import logging
from datetime import datetime

# Configuration
EXCLUDE_DIRS = {'venv', 'win_venv', '.venv', '.win_venv', 'browser/2', '_snapshots', '_update_ver', 'scrapers/2', ".git"}
EXCLUDE_PATTERNS = {'snapshot_*', 'update_*'}
EXCLUDE_FILES = {'social.db', 'config.json', "upload_queue*"}  # Include temp SQLite files if needed
VERSION_FILE = 'version'
SNAPSHOT_DIR = './_snapshots'
UPDATE_DIR = './_update_ver'

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_current_version():
    """Read version from file; no auto-increment."""
    try:
        with open(VERSION_FILE, 'r') as f:
            return f.read().strip()
    except Exception as e:
        logging.error(f"Failed to read version file: {e}")
        raise


def should_exclude(path):
    rel_path = os.path.relpath(path)
    path_obj = Path(rel_path)

    # 1. Check if full path or parent starts with excluded dir
    for excluded in EXCLUDE_DIRS:
        if rel_path == str(excluded) or rel_path.startswith(str(excluded) + os.sep):
            return True

    # 2. Check if any path part matches excluded dir names
    if any(part in EXCLUDE_DIRS for part in path_obj.parts):
        return True

    # 3. Check if file name is in EXCLUDE_FILES
    if path_obj.name in EXCLUDE_FILES:
        return True

    # 4. Exclude patterns like snapshot_*, update_*
    if any(path_obj.match(pattern) for pattern in EXCLUDE_PATTERNS):
        return True

    return False
def get_file_checksum(filepath):
    hash_sha256 = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        logging.error(f"Failed to compute checksum for {filepath}: {e}")
        raise


def get_pip_freeze():
    try:
        result = subprocess.run(['pip-chill'], capture_output=True, text=True, check=True)
        return result.stdout.splitlines()
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to run pip freeze: {e}")
        raise


def create_snapshot(version):
    snapshot = {
        'version': version,
        'files': {},
        'directories': [],
        'pip': get_pip_freeze()
    }

    for root, dirs, files in os.walk('.'):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if not should_exclude(os.path.join(root, d))]

        rel_root = os.path.relpath(root)
        if rel_root != '.' and not should_exclude(rel_root):
            snapshot['directories'].append(rel_root)

        for file in files:
            filepath = os.path.join(root, file)
            if should_exclude(filepath):
                continue
            rel_path = os.path.relpath(filepath)
            snapshot['files'][rel_path] = get_file_checksum(filepath)

    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    snapshot_name = os.path.join(SNAPSHOT_DIR, f'snapshot_{version}.json')
    with open(snapshot_name, 'w') as f:
        json.dump(snapshot, f, indent=2)

    return snapshot_name


def load_snapshot(version):
    snapshot_name = os.path.join(SNAPSHOT_DIR, f'snapshot_{version}.json')
    with open(snapshot_name, 'r') as f:
        return json.load(f)


def create_update_package(new_version, full=False):
    """Create update package using diff between latest snapshot and current state."""
    timestamp = int(datetime.now().timestamp())
    suffix = "major" if full else "minor"
    zip_name = f"update_{suffix}_{timestamp}.zip"
    zip_path = os.path.join(UPDATE_DIR, zip_name)

    # Create new snapshot (current state)
    new_snapshot_path = create_snapshot(new_version)
    try:
        with open(new_snapshot_path, 'r') as f:
            new_snapshot_data = json.load(f)
    except Exception as e:
        logging.error(f"Failed to load new snapshot: {e}")
        raise

    # Try to find the most recent snapshot for the same version OR any prior version
    # We look for any existing snapshot_{new_version}.json as "last build"
    old_snapshot_data = None
    old_version = None

    # Prefer: previous build with same version (incremental dev)
    # Fallback: any other version (last known state)
    candidate_versions = []

    # Scan _snapshots/ for all version files
    if os.path.exists(SNAPSHOT_DIR):
        for fname in os.listdir(SNAPSHOT_DIR):
            if fname.startswith('snapshot_') and fname.endswith('.json'):
                try:
                    ver = fname[len('snapshot_'):-len('.json')]
                    candidate_versions.append(ver)
                except:
                    continue

    # Sort by version descending
    try:
        candidate_versions.sort(key=version_to_tuple, reverse=True)
    except:
        pass  # fallback to raw list

    # First try: same version (incremental build)
    for ver in candidate_versions:
        if ver == new_version:
            old_snapshot_path = os.path.join(SNAPSHOT_DIR, f'snapshot_{ver}.json')
            if os.path.exists(old_snapshot_path) and old_snapshot_path != new_snapshot_path:
                try:
                    with open(old_snapshot_path, 'r') as f:
                        old_snapshot_data = json.load(f)
                    old_version = ver
                    logging.info(f"Found previous build for version {ver} to diff against.")
                    break
                except Exception as e:
                    logging.warning(f"Could not load previous snapshot {old_snapshot_path}: {e}")

    # Fallback: latest different version
    if old_snapshot_data is None:
        for ver in candidate_versions:
            if ver != new_version:
                old_snapshot_path = os.path.join(SNAPSHOT_DIR, f'snapshot_{ver}.json')
                try:
                    with open(old_snapshot_path, 'r') as f:
                        old_snapshot_data = json.load(f)
                    old_version = ver
                    logging.info(f"Using last known version {ver} for diff.")
                    break
                except Exception as e:
                    logging.warning(f"Could not load snapshot {ver}: {e}")

    # Default: empty base (full update)
    if old_snapshot_data is None:
        old_snapshot_data = {'files': {}, 'directories': [], 'pip': []}
        old_version = None

    # --- Compute differences ---
    old_files = old_snapshot_data['files']
    new_files = new_snapshot_data['files']
    old_dirs = set(old_snapshot_data.get('directories', []))
    new_dirs = set(new_snapshot_data.get('directories', []))

    added_files = []
    modified_files = []
    for file, checksum in new_files.items():
        if file not in old_files:
            added_files.append(file)
        elif old_files[file] != checksum:
            modified_files.append(file)

    deleted_files = [f for f in old_files if f not in new_files]
    added_dirs = list(new_dirs - old_dirs)
    deleted_dirs = list(old_dirs - new_dirs)

    # If --full, include everything
    if full:
        added_files = list(new_files.keys())
        modified_files = []
        deleted_files = []
        added_dirs = list(new_dirs)
        deleted_dirs = []

    # --- Create update package ---
    os.makedirs(UPDATE_DIR, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Always include the new snapshot
        zipf.write(new_snapshot_path, os.path.basename(new_snapshot_path))

        # Add only changed files
        for file in added_files + modified_files:
            if os.path.exists(file):
                zipf.write(file)
            else:
                logging.warning(f"File not found (but in snapshot): {file}")

        # Metadata
        metadata = {
            'from_version': old_version if old_version else "any",
            'to_version': new_version,
            'timestamp': timestamp,
            'added_files': added_files,
            'modified_files': modified_files,
            'deleted_files': deleted_files,
            'added_dirs': added_dirs,
            'deleted_dirs': deleted_dirs,
            'old_pip': old_snapshot_data.get('pip', []),
            'new_pip': new_snapshot_data.get('pip', [])
        }
        zipf.writestr('update_metadata.json', json.dumps(metadata, indent=2))

    logging.info(f"Created update package: {zip_path}")
    logging.info(f"  Changes: +{len(added_files)} files, ±{len(modified_files)}, -{len(deleted_files)} files")
    return zip_path

def main():
    parser = argparse.ArgumentParser(description="Create update package using manual version from ./version.")
    parser.add_argument('--full', action='store_true', help="Mark as major update (full package)")
    args = parser.parse_args()

    new_version = get_current_version()

    print(f"Using version from {VERSION_FILE}: {new_version}")

    # Create snapshot
    snapshot_name = create_snapshot(new_version)
    print(f"Created snapshot: {snapshot_name}")

    # Create update package
    zip_name = create_update_package(new_version, full=args.full)
    print(f"Created update package: {zip_name}")


if __name__ == '__main__':
    main()