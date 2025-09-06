import os
import sys
import json
import re
import logging
import requests
import subprocess
import threading
import tkinter as tk
from tkinter import ttk
from urllib.parse import urlencode
from docx import Document
import time
import platform
import psutil

# --- Configuration ---
VERSION_FILE = 'version'
UPDATE_DIR = './_update_ver'
VERSIONS_DOCX_URL = 'https://disk.yandex.ru/i/vRkoM0xCSe1d_w'  # Public link to updates.docx
VERSIONS_DOCX_PATH = 'update.docx'

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global root
root = None


def fetch(public_key, write_as='update.docx'):
    """Download file from Yandex Disk with progress."""
    api_url = 'https://cloud-api.yandex.net/v1/disk/public/resources/download?'
    download_url = api_url + urlencode({'public_key': public_key.strip()})
    try:
        response = requests.get(download_url)
        response.raise_for_status()
        direct_url = response.json()['href']

        with requests.get(direct_url, stream=True) as r:
            r.raise_for_status()
            total = int(r.headers.get('content-length', 0))
            downloaded = 0
            with open(write_as, 'wb') as f:
                for chunk in r.iter_content(4096):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        yield total, downloaded
    except Exception as e:
        logging.error(f"Download failed: {e}")
        raise


def get_current_version():
    """Read current version from file."""
    try:
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except:
        return "0.0.0"


def version_to_tuple(version):
    """Convert version string to tuple for comparison."""
    try:
        return tuple(map(int, version.split('.')))
    except:
        return (0, 0, 0)


def parse_versions_docx(path):
    """Parse update rules from docx: '1.0.0 -> 1.0.2, https://disk.yandex.ru/d/...'"""
    if not os.path.exists(path):
        logging.error(f"File not found: {path}")
        return []
    try:
        doc = Document(path)
        updates = []
        for p in doc.paragraphs:
            text = p.text.strip()
            match = re.match(
                r'(\d+\.\d+\.\d+)\s*->\s*(\d+\.\d+\.\d+)\s*,\s*(https://disk\.yandex\.ru/d/[\w-]+)',
                text)
            if match:
                updates.append(match.groups())
        return sorted(updates, key=lambda x: version_to_tuple(x[1]))
    except Exception as e:
        logging.error(f"Failed to parse .docx: {e}")
        return []


def get_latest_version(updates):
    """Get latest version from update list."""
    return updates[-1][1] if updates else "N/A"


def get_updates_chain(current, updates):
    """Get list of updates needed to reach latest."""
    chain = []
    curr = current
    while True:
        candidates = [
            (fv, tv, url) for fv, tv, url in updates
            if version_to_tuple(fv) <= version_to_tuple(curr)
        ]
        if not candidates:
            break
        best = max(candidates, key=lambda x: version_to_tuple(x[1]))
        if version_to_tuple(best[1]) <= version_to_tuple(curr):
            break
        chain.append(best)
        curr = best[1]
    return chain


def start_server_and_exit():
    """Close updater and directly run `launch.py` in THIS process (so we see output)."""
    global root
    try:
        root.quit()
        root.destroy()
    except:
        pass

    logging.info("Starting launch.py and handing over control...")

    try:
        import launch
        launch.start()
    except Exception as e:
        logging.error(f"Failed to start server: {e}")

    sys.exit(0)


def restart_updater():
    """Robustly restart updater across Windows and macOS with retry and cleanup."""
    global root
    max_attempts = 3
    retry_delay = 1  # seconds

    # Clean up Tkinter
    try:
        if root:
            root.quit()
            root.destroy()
    except Exception as e:
        logging.error(f"Error during Tkinter cleanup: {e}")

    # Get current process info
    current_pid = os.getpid()
    logging.info(f"Attempting to restart updater (PID: {current_pid})...")

    # Ensure Python executable path is valid
    python_exe = sys.executable
    if not os.path.exists(python_exe):
        logging.error(f"Python executable not found: {python_exe}")
        start_server_and_exit()
        return

    # Normalize path for cross-platform compatibility
    script_path = os.path.abspath(sys.argv[0])

    # Prepare command
    cmd = [python_exe, script_path] + sys.argv[1:]

    for attempt in range(max_attempts):
        try:
            logging.info(f"Restart attempt {attempt + 1}/{max_attempts}")

            # Platform-specific process spawning
            if platform.system() == "Windows":
                # Use CREATE_NEW_PROCESS_GROUP to allow proper detachment
                subprocess.Popen(
                    cmd,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            else:  # macOS/Unix
                # Use subprocess to start detached process
                subprocess.Popen(
                    cmd,
                    start_new_session=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

            # Verify new process started
            time.sleep(0.5)  # Give new process time to start
            current_process = psutil.Process(current_pid)
            children = current_process.children(recursive=True)
            if children:
                logging.info("New updater process successfully started")

                # Clean up any remaining resources
                try:
                    current_process.terminate()
                except:
                    pass

                sys.exit(0)
            else:
                logging.warning("New process not detected")

        except Exception as e:
            logging.error(f"Restart attempt {attempt + 1} failed: {e}")

        if attempt < max_attempts - 1:
            logging.info(f"Waiting {retry_delay} seconds before retry...")
            time.sleep(retry_delay)

    logging.error("All restart attempts failed. Starting server instead...")
    start_server_and_exit()


class UpdaterApp:
    def __init__(self, master):
        self.root = master
        master.title("Project Updater")
        master.geometry("450x250")
        master.resizable(False, False)

        self.current_version = get_current_version()
        self.latest_version = "Checking..."

        ttk.Label(master, text="Current Version:").pack(pady=(20, 0))
        self.current_label = ttk.Label(master, text=self.current_version, font=("Arial", 12, "bold"))
        self.current_label.pack()

        ttk.Label(master, text="Latest Available Version:").pack(pady=(10, 0))
        self.latest_label = ttk.Label(master, text=self.latest_version, font=("Arial", 12, "bold"))
        self.latest_label.pack()

        self.progress = ttk.Progressbar(master, length=400, mode='determinate')
        self.progress.pack(pady=15)

        ttk.Label(master, text="Status:").pack()
        self.status_label = ttk.Label(master, text="Initializing...")
        self.status_label.pack()

        threading.Thread(target=self.auto_update, daemon=True).start()

    def auto_update(self):
        try:
            self.status_label.config(text="Fetching update info...")
            self.root.update_idletasks()

            # Download versions file
            try:
                for _ in fetch(VERSIONS_DOCX_URL, VERSIONS_DOCX_PATH):
                    pass
            except Exception as e:
                logging.error(f"Failed to download update list: {e}")
                self.status_label.config(text="Network error. Starting app...")
                self.root.after(1000, start_server_and_exit)
                return

            updates = parse_versions_docx(VERSIONS_DOCX_PATH)
            self.latest_version = get_latest_version(updates)
            self.latest_label.config(text=self.latest_version)

            # Case 1: Already up to date → just start server
            if self.current_version == self.latest_version:
                self.status_label.config(text="Up to date. Starting server...")
                self.root.after(1000, start_server_and_exit)
                return

            # Case 2: Need updates
            chain = get_updates_chain(self.current_version, updates)
            if not chain:
                self.status_label.config(text="No valid update path. Starting server...")
                self.root.after(1000, start_server_and_exit)
                return

            # Download all needed updates
            zip_files = []
            from_map = {}
            total = len(chain)

            for i, (fv, tv, url) in enumerate(chain, 1):
                self.status_label.config(text=f"Downloading {tv} ({i}/{total})...")
                os.makedirs(UPDATE_DIR, exist_ok=True)
                path = os.path.join(UPDATE_DIR, f'update_{tv}.zip')
                try:
                    for total_size, downloaded in fetch(url.strip(), path):
                        if total_size:
                            self.progress['value'] = downloaded / total_size * 100
                        self.root.update_idletasks()
                except Exception as e:
                    logging.error(f"Download failed ({url}): {e}")
                    continue
                zip_files.append(path)
                from_map[tv] = fv
                self.progress['value'] = 0

            if not zip_files:
                self.status_label.config(text="All downloads failed. Starting server...")
                self.root.after(1000, start_server_and_exit)
                return

            # Apply updates
            self.status_label.config(text="Applying updates...")
            self.root.update_idletasks()

            cmd = [sys.executable, 'apply_update.py'] + (['--many'] if len(zip_files) > 1 else []) + zip_files
            env = os.environ.copy()
            env['FROM_VERSIONS'] = json.dumps(from_map)

            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"Update failed: {result.stderr}")
                self.status_label.config(text="Update failed. Starting server anyway...")
                self.root.after(1000, start_server_and_exit)
                return

            # Save new version
            latest_ver = chain[-1][1]
            with open(VERSION_FILE, 'w', encoding='utf-8') as f:
                f.write(latest_ver + '\n')

            # RESTART updater
            self.status_label.config(text="Update applied. Restarting updater...")
            logging.info("Updater will restart to apply changes...")
            self.root.after(1000, restart_updater)
            return

        except Exception as e:
            logging.error(f"Updater failed: {e}")
            self.status_label.config(text="Error. Starting server...")
            self.root.after(1500, start_server_and_exit)


if __name__ == '__main__':
    root = tk.Tk()
    app = UpdaterApp(root)
    root.mainloop()