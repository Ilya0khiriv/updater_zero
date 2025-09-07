import os
import hashlib
import zipfile
import json
import subprocess
from pathlib import Path
import argparse
import logging
import re
from datetime import datetime
import shutil

# Configuration
EXCLUDE_DIRS = {'venv', 'win_venv', '.venv', '.win_venv', 'browser/2', '_snapshots', '_update_ver', 'scrapers/2', ".git", "2"}
EXCLUDE_PATTERNS = {'snapshot_*', 'update_*'}
EXCLUDE_FILES = {'social.db', 'config.json', "upload_queue_backup.db"}
VERSION_FILE = 'version'
SNAPSHOT_DIR = './_snapshots'
UPDATE_DIR = './_update_ver'
SNAPSHOT_BACKUP_DIR = './_snapshots_backup'

# Setup logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('snapshooter.log', mode='a')
    ]
)

def validate_version(version):
    """Validate version string (e.g., semantic versioning or simple format)."""
    semver_pattern = r'^\d+\.\d+\.\d+$'
    if not re.match(semver_pattern, version):
        logging.warning(f"Version '{version}' does not follow semantic versioning (x.y.z).")
    return version

def get_current_version():
    """Read version from file; no auto-increment."""
    try:
        if not os.path.exists(VERSION_FILE):
            raise FileNotFoundError(f"Version file '{VERSION_FILE}' not found.")
        with open(VERSION_FILE, 'r') as f:
            version = f.read().strip()
            if not version:
                raise ValueError(f"Version file '{VERSION_FILE}' is empty.")
            return validate_version(version)
    except Exception as e:
        logging.error(f"Failed to read version file: {e}")
        raise

def should_exclude(path):
    """Check if a path should be excluded from snapshot."""
    try:
        rel_path = os.path.relpath(path)
        path_obj = Path(rel_path)

        # Check if full path or parent starts with excluded dir
        for excluded in EXCLUDE_DIRS:
            if rel_path == str(excluded) or rel_path.startswith(str(excluded) + os.sep):
                return True

        # Check if any path part matches excluded dir names
        if any(part in EXCLUDE_DIRS for part in path_obj.parts):
            return True

        # Check if file name is in EXCLUDE_FILES
        if path_obj.name in EXCLUDE_FILES:
            return True

        # Exclude patterns like snapshot_*, update_*
        if any(path_obj.match(pattern) for pattern in EXCLUDE_PATTERNS):
            return True

        return False
    except Exception as e:
        logging.error(f"Error checking exclusion for {path}: {e}")
        return True  # Exclude on error to be safe

def get_file_checksum(filepath):
    """Compute SHA256 checksum of a file."""
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
    """Get list of installed Python packages using pip-chill."""
    try:
        result = subprocess.run(['pip-chill'], capture_output=True, text=True, check=True)
        return result.stdout.splitlines()
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to run pip-chill: {e}")
        raise
    except FileNotFoundError:
        logging.error("pip-chill not found. Ensure it is installed.")
        raise

def create_snapshot(version):
    """Create a snapshot of the current project state."""
    snapshot = {
        'version': version,
        'timestamp': datetime.now().isoformat(),
        'files': {},
        'directories': [],
        'pip': get_pip_freeze()
    }

    try:
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
        snapshot_name = os.path.join(SNAPSHOT_DIR, f'snapshot_{version}_{int(datetime.now().timestamp())}.json')

        # Backup existing snapshot if it exists
        if os.path.exists(snapshot_name):
            os.makedirs(SNAPSHOT_BACKUP_DIR, exist_ok=True)
            backup_path = os.path.join(SNAPSHOT_BACKUP_DIR, f'snapshot_{version}_{int(datetime.now().timestamp())}_backup.json')
            shutil.copy2(snapshot_name, backup_path)
            logging.info(f"Backed up existing snapshot to {backup_path}")

        with open(snapshot_name, 'w') as f:
            json.dump(snapshot, f, indent=2)

        return snapshot_name
    except Exception as e:
        logging.error(f"Failed to create snapshot: {e}")
        raise

def load_snapshot(snapshot_path):
    """Load a snapshot file and validate it."""
    try:
        with open(snapshot_path, 'r') as f:
            data = json.load(f)
        # Validate snapshot structure
        required_keys = {'version', 'files', 'directories', 'pip'}
        if not all(key in data for key in required_keys):
            raise ValueError(f"Invalid snapshot structure in {snapshot_path}")
        return data
    except Exception as e:
        logging.error(f"Failed to load snapshot {snapshot_path}: {e}")
        raise

def list_snapshots():
    """List all available snapshots with version and timestamp."""
    snapshots = []
    if os.path.exists(SNAPSHOT_DIR):
        for fname in os.listdir(SNAPSHOT_DIR):
            if fname.startswith('snapshot_') and fname.endswith('.json'):
                try:
                    snapshot_path = os.path.join(SNAPSHOT_DIR, fname)
                    with open(snapshot_path, 'r') as f:
                        data = json.load(f)
                    version = data.get('version', 'unknown')
                    timestamp = data.get('timestamp', 'unknown')
                    snapshots.append((snapshot_path, version, timestamp))
                except Exception as e:
                    logging.warning(f"Skipping invalid snapshot {fname}: {e}")
    return sorted(snapshots, key=lambda x: x[2], reverse=True)  # Sort by timestamp

def select_snapshot():
    """Interactive snapshot selection using a text-based menu."""
    snapshots = list_snapshots()
    if not snapshots:
        print("No snapshots found. Creating a full update.")
        return None, None

    print("\nAvailable snapshots:")
    print("Use number keys to select a snapshot (or 0 for full update):")
    for i, (path, version, timestamp) in enumerate(snapshots, 1):
        print(f"{i}. Version: {version}, Timestamp: {timestamp} ({path})")
    print("0. Create full update (no comparison)")

    while True:
        try:
            choice = input("Select snapshot (0-{}): ".format(len(snapshots)))
            choice = int(choice)
            if choice == 0:
                return None, None
            if 1 <= choice <= len(snapshots):
                return snapshots[choice-1][0], snapshots[choice-1][1]
            print(f"Invalid choice. Please enter a number between 0 and {len(snapshots)}.")
        except ValueError:
            print("Please enter a valid number.")

def create_update_package(new_version, full=False):
    """Create update package using diff between selected snapshot and current state."""
    timestamp = int(datetime.now().timestamp())
    suffix = "major" if full else "minor"
    zip_name = f"update_{suffix}_{timestamp}.zip"
    zip_path = os.path.join(UPDATE_DIR, zip_name)

    # Create new snapshot (current state)
    new_snapshot_path = create_snapshot(new_version)
    new_snapshot_data = load_snapshot(new_snapshot_path)

    # Select previous snapshot
    old_snapshot_path, old_version = select_snapshot() if not full else (None, None)

    if old_snapshot_path:
        old_snapshot_data = load_snapshot(old_snapshot_path)
    else:
        old_snapshot_data = {'files': {}, 'directories': [], 'pip': []}
        old_version = "any"

    # Compute differences
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

    # Create update package
    try:
        os.makedirs(UPDATE_DIR, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Include the new snapshot
            zipf.write(new_snapshot_path, os.path.basename(new_snapshot_path))

            # Add changed files
            for file in added_files + modified_files:
                if os.path.exists(file):
                    zipf.write(file)
                else:
                    logging.warning(f"File not found (but in snapshot): {file}")

            # Metadata
            metadata = {
                'from_version': old_version,
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
    except Exception as e:
        logging.error(f"Failed to create update package: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Create update package using manual version from ./version.")
    parser.add_argument('--full', action='store_true', help="Mark as major update (full package)")
    args = parser.parse_args()

    try:
        new_version = get_current_version()
        print(f"Using version from {VERSION_FILE}: {new_version}")

        # Create snapshot
        snapshot_name = create_snapshot(new_version)
        print(f"Created snapshot: {snapshot_name}")

        # Create update package
        zip_name = create_update_package(new_version, full=args.full)
        print(f"Created update package: {zip_name}")
    except Exception as e:
        logging.error(f"Script failed: {e}")
        raise

if __name__ == '__main__':
    main()