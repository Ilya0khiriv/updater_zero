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
VERSIONS_DOCX_URL = 'https://disk.yandex.ru/i/yWKvtV4nTA_txA'  # Public link to updates.docx
VERSIONS_DOCX_PATH = 'update.docx'

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global root
root = None

# Required packages by platform
REQUIRED_PACKAGES = {
    "universal": [
        "absl-py==2.3.1",
        "aiofiles==24.1.0",
        "aiohappyeyeballs==2.6.1",
        "aiohttp==3.12.15",
        "aiosignal==1.4.0",
        "annotated-types==0.7.0",
        "antlr4-python3-runtime==4.9.3",
        "anyascii==0.3.3",
        "anyio==4.10.0",
        "attrs==25.3.0",
        "audioread==3.0.1",
        "babel==2.17.0",
        "bangla==0.0.5",
        "blinker==1.9.0",
        "blis==1.2.1",
        "bnnumerizer==0.0.2",
        "bnunicodenormalizer==0.1.7",
        "catalogue==2.0.10",
        "certifi==2025.8.3",
        "cffi==1.17.1",
        "charset-normalizer==3.4.3",
        "click==8.2.1",
        "cloudpathlib==0.22.0",
        "coloredlogs==15.0.1",
        "confection==0.1.5",
        "contourpy==1.3.3",
        "coqpit-config==0.2.1",
        "coqui-tts==0.27.1",
        "coqui-tts-trainer==0.3.1",
        "cycler==0.12.1",
        "cymem==2.0.11",
        "Cython==3.1.3",
        "dateparser==1.1.8",
        "decorator==5.2.1",
        "distro==1.9.0",
        "docopt==0.6.2",
        "einops==0.8.1",
        "encodec==0.1.1",
        "fastapi==0.116.1",
        "filelock==3.19.1",
        "Flask==3.1.2",
        "flatbuffers==25.2.10",
        "fonttools==4.59.2",
        "frozenlist==1.7.0",
        "fsspec==2025.9.0",
        "g2pkk==0.1.2",
        "grpcio==1.74.0",
        "gruut==2.4.0",
        "gruut-ipa==0.13.0",
        "gruut_lang_de==2.0.1",
        "gruut_lang_en==2.0.1",
        "gruut_lang_es==2.0.1",
        "gruut_lang_fr==2.0.2",
        "h11==0.16.0",
        "hangul-romanize==0.1.0",
        "hf-xet==1.1.9",
        "httpcore==1.0.9",
        "httpx==0.28.1",
        "huggingface-hub==0.34.4",
        "humanfriendly==10.0",
        "idna==3.10",
        "inflect==7.5.0",
        "itsdangerous==2.2.0",
        "jamo==0.4.1",
        "jieba==0.42.1",
        "Jinja2==3.1.6",
        "jiter==0.10.0",
        "joblib==1.5.2",
        "jsonlines==1.2.0",
        "kiwisolver==1.4.9",
        "langcodes==3.5.0",
        "language_data==1.3.0",
        "lazy_loader==0.4",
        "librosa==0.11.0",
        "llvmlite==0.44.0",
        "marisa-trie==1.3.1",
        "Markdown==3.9",
        "markdown-it-py==4.0.0",
        "MarkupSafe==3.0.2",
        "matplotlib==3.10.6",
        "mdurl==0.1.2",
        "monotonic-alignment-search==0.2.0",
        "more-itertools==10.8.0",
        "mpmath==1.3.0",
        "msgpack==1.1.1",
        "multidict==6.6.4",
        "murmurhash==1.0.13",
        "networkx==2.8.8",
        "nltk==3.9.1",
        "num2words==0.5.14",
        "numba==0.61.2",
        "numpy==1.26.4",
        "omegaconf==2.3.0",
        "onnxruntime==1.22.1",
        "openai==1.106.1",
        "packaging==25.0",
        "pandas==1.5.3",
        "pillow==11.3.0",
        "platformdirs==4.4.0",
        "pooch==1.8.2",
        "preshed==3.0.10",
        "propcache==0.3.2",
        "protobuf==6.32.0",
        "psutil==7.0.0",
        "pycparser==2.22",
        "pydantic==2.11.7",
        "pydantic_core==2.33.2",
        "pydub==0.25.1",
        "Pygments==2.19.2",
        "pynndescent==0.5.13",
        "pyparsing==3.2.3",
        "pypinyin==0.55.0",
        "pysbd==0.3.4",
        "python-crfsuite==0.9.11",
        "python-dateutil==2.9.0.post0",
        "python-multipart==0.0.20",
        "pytz==2025.2",
        "PyYAML==6.0.2",
        "razdel==0.5.0",
        "regex==2025.9.1",
        "requests==2.32.5",
        "rich==14.1.0",
        "ruaccent==1.5.8.3",
        "safetensors==0.6.2",
        "scikit-learn==1.7.1",
        "scipy==1.16.1",
        "sentencepiece==0.2.1",
        "shellingham==1.5.4",
        "six==1.17.0",
        "smart_open==7.3.0.post1",
        "sniffio==1.3.1",
        "soundfile==0.13.1",
        "soxr==0.5.0.post1",
        "spacy==3.8.7",
        "spacy-legacy==3.0.12",
        "spacy-loggers==1.0.5",
        "srsly==2.5.1",
        "starlette==0.47.3",
        "SudachiDict-core==20250825",
        "SudachiPy==0.6.10",
        "sympy==1.14.0",
        "tensorboard==2.20.0",
        "tensorboard-data-server==0.7.2",
        "thinc==8.3.4",
        "threadpoolctl==3.6.0",
        "tiktoken==0.11.0",
        "tokenizers==0.22.0",
        "torch==2.8.0",
        "torchaudio==2.8.0",
        "tqdm==4.67.1",
        "trainer==0.0.36",
        "transformers==4.56.1",
        "typeguard==4.4.4",
        "typer==0.17.4",
        "typing-inspection==0.4.1",
        "typing_extensions==4.15.0",
        "tzlocal==5.3.1",
        "umap-learn==0.5.9.post2",
        "Unidecode==1.4.0",
        "urllib3==2.5.0",
        "uvicorn==0.35.0",
        "wasabi==1.1.3",
        "weasel==0.4.1",
        "Werkzeug==3.1.3",
        "wrapt==1.17.3",
        "yarl==1.20.1"
    ],
    "mac_only": [
        "mlx==0.29.0",
        "mlx-metal==0.29.0",
        "mlx-whisper==0.4.3"
    ],
    "linux_only": [
        "openai-whisper==20250625"
    ]
}


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
    """Parse update rules from docx: '1.0.0 -> 1.0.2,   https://disk.yandex.ru/d/...  '"""
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


def ensure_packages():
    """Uninstall old packages and install required ones."""
    logging.info("Checking and installing required packages...")

    # Uninstall old packages
    for package in ["TTS", "tts-models", "coqpit"]:
        try:
            subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", package], check=True)
            logging.info(f"Uninstalled {package}")
        except subprocess.CalledProcessError:
            logging.warning(f"Could not uninstall {package} (may not be installed)")

    # Install coqpit-config and coqui-tts
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "coqpit-config"], check=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "-U", "coqui-tts"], check=True)
        logging.info("Installed coqpit-config and updated coqui-tts")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to install coqui-tts or coqpit-config: {e}")

    # Determine platform-specific packages
    system = platform.system().lower()
    pkgs = REQUIRED_PACKAGES["universal"].copy()
    if system == "darwin":
        pkgs += REQUIRED_PACKAGES["mac_only"]
    elif system == "linux":
        pkgs += REQUIRED_PACKAGES["linux_only"]

    # Install all required packages
    try:
        subprocess.run([sys.executable, "-m", "pip", "install"] + pkgs, check=True)
        logging.info("All required packages installed.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to install some packages: {e}")


def start_server_and_exit():
    """Close updater and start server_monitor.py after ensuring packages."""
    global root
    try:
        root.quit()
        root.destroy()
    except:
        pass

    logging.info("Ensuring packages before starting server...")
    ensure_packages()

    logging.info("Starting server_monitor.py...")
    try:
        # Run in the same process so output is visible
        subprocess.run([sys.executable, 'server_monitor.py'], check=True)
    except Exception as e:
        logging.error(f"Failed to start server_monitor.py: {e}")

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

    python_exe = sys.executable
    if not os.path.exists(python_exe):
        logging.error(f"Python executable not found: {python_exe}")
        start_server_and_exit()
        return

    script_path = os.path.abspath(sys.argv[0])
    cmd = [python_exe, script_path] + sys.argv[1:]

    for attempt in range(max_attempts):
        try:
            logging.info(f"Restart attempt {attempt + 1}/{max_attempts}")

            if platform.system() == "Windows":
                subprocess.Popen(
                    cmd,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            else:
                subprocess.Popen(
                    cmd,
                    start_new_session=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

            time.sleep(0.5)
            current_process = psutil.Process(current_pid)
            children = current_process.children(recursive=True)
            if children:
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

            # Case 1: Already up to date
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

            # Download updates
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

            # Restart updater
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