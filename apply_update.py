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

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

VERSION_FILE = 'version'


def version_to_tuple(version):
    try:
        return tuple(map(int, version.split('.')))
    except ValueError:
        logging.error(f"Invalid version format: {version}")
        raise


def force_remove(path):
    """Force remove file or directory, even if read-only."""
    def handle_remove_readonly(func, path, exc_info):
        # Make file writable and retry
        os.chmod(path, stat.S_IWRITE)
        func(path)

    if os.path.isfile(path):
        try:
            os.chmod(path, stat.S_IWRITE)  # Remove read-only
            os.remove(path)
            logging.info(f"Removed file: {path}")
        except Exception as e:
            logging.warning(f"Retry: force delete failed for {path}: {e}")
            # Fallback: use shutil with error handler
            shutil.rmtree(os.path.dirname(path), onerror=handle_remove_readonly)

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

            # --- PHASE 1: Delete all files/dirs marked for deletion
            for file in metadata.get('deleted_files', []):
                file_path = os.path.abspath(file)
                if os.path.exists(file_path):
                    force_remove(file_path)

            for dir_path in metadata.get('deleted_dirs', []):
                full_path = os.path.abspath(dir_path)
                if os.path.exists(full_path):
                    force_remove(full_path)

            # --- PHASE 2: Extract directly — overwrite everything
            for zip_info in zipf.infolist():
                # Skip metadata and snapshot (already processed)
                if zip_info.filename in ['update_metadata.json', os.path.basename(snapshot_file)]:
                    continue

                target_path = os.path.abspath(zip_info.filename)
                target_dir = os.path.dirname(target_path)

                # If it's a directory entry (ends with /), just ensure it exists
                if zip_info.filename.endswith('/'):
                    os.makedirs(target_path, exist_ok=True)
                    continue

                # Ensure parent dir exists
                os.makedirs(target_dir, exist_ok=True)

                # HARD: Remove existing file if present
                if os.path.exists(target_path):
                    force_remove(target_path)

                # Extract fresh copy
                zipf.extract(zip_info, path=os.getcwd())

            # --- PHASE 3: Recreate added directories (ensure)
            for dir_path in metadata.get('added_dirs', []):
                os.makedirs(os.path.abspath(dir_path), exist_ok=True)

            # --- PHASE 4: Update pip dependencies
            new_pip = metadata.get('new_pip', [])
            if new_pip:
                req_file = 'temp_requirements_update.txt'
                with open(req_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(new_pip))
                try:
                    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', req_file], check=True)
                    logging.info("Dependencies updated.")
                except subprocess.CalledProcessError as e:
                    logging.error(f"Pip install failed: {e}")
                    raise
                finally:
                    if os.path.exists(req_file):
                        force_remove(req_file)

            # --- PHASE 5: Update version
            try:
                with open(VERSION_FILE, 'w', encoding='utf-8') as f:
                    f.write(to_version + '\n')
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

    # Extract snapshot filename from first ZIP to skip during extract
    try:
        with zipfile.ZipFile(zip_files[0], 'r') as zf:
            snapshot_file = [f for f in zf.namelist() if f.startswith('snapshot_') and f.endswith('.json')]
            snapshot_file = snapshot_file[0] if snapshot_file else 'snapshot_.json'
    except:
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
    sys.exit(0)


if __name__ == '__main__':
    main()


