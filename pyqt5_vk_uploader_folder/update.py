import sys
import os
import json
import zipfile
import shutil
import stat
import requests
from urllib.parse import urlencode
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QProgressBar, QApplication
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont


VERSION_FILE = "version"


def extract_public_key(yandex_url):
    """Extract public key from Yandex.Disk public link like https://disk.yandex.ru/i/KEY"""
    if '/i/' in yandex_url:
        key = yandex_url.split('/i/', 1)[1]
        # Remove any query params or fragments
        key = key.split('?')[0].split('#')[0].strip()
        return key
    raise ValueError("Invalid Yandex.Disk URL")


def force_remove(path):
    def handle_remove_readonly(func, p, exc_info):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    path = os.path.abspath(path)
    if os.path.isfile(path):
        try:
            os.chmod(path, stat.S_IWRITE)
            os.remove(path)
        except Exception:
            try:
                shutil.rmtree(os.path.dirname(path), onerror=handle_remove_readonly)
            except Exception:
                pass
    elif os.path.isdir(path):
        shutil.rmtree(path, onerror=handle_remove_readonly)


class UpdateWorker(QThread):
    finished = pyqtSignal(object, str)  # (update_info or None, error_msg)
    current_version_fetched = pyqtSignal(int)

    def run(self):
        current_version = 0
        try:
            if os.path.exists(VERSION_FILE):
                with open(VERSION_FILE, "r") as f:
                    current_version = int(f.read().strip())
            self.current_version_fetched.emit(current_version)
        except Exception as e:
            self.finished.emit(None, f"Failed to read version: {e}")
            return

        # CORRECT RAW URL — no /blob/, no spaces
        url = "https://raw.githubusercontent.com/Ilya0khiriv/updater_zero/main/pyqt5_vk_uploader_folder/update.json"

        try:
            with requests.get(url, timeout=10) as response:
                response.raise_for_status()
                data = response.json()

            next_ver = current_version + 1
            next_ver_str = str(next_ver)

            if next_ver_str in data and isinstance(data[next_ver_str], str):
                link = data[next_ver_str].strip()
                if link:
                    update_info = {
                        "version": next_ver,          # logical version: 1, 2, ...
                        "link": link,                 # Yandex public link
                        "current_version": current_version
                    }
                    self.finished.emit(update_info, "")
                    return

            self.finished.emit(None, "")
        except Exception as e:
            self.finished.emit(None, f"Network/JSON error: {e}")


class YandexDownloaderThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)  # local zip path
    failed = pyqtSignal(str)

    def __init__(self, yandex_url, save_path):
        super().__init__()
        self.yandex_url = yandex_url
        self.save_path = save_path

    def run(self):
        try:
            public_key = extract_public_key(self.yandex_url)
            api_url = 'https://cloud-api.yandex.net/v1/disk/public/resources/download?'
            download_url = api_url + urlencode({'public_key': public_key})

            resp = requests.get(download_url, timeout=15)
            resp.raise_for_status()
            direct_url = resp.json()['href']

            with requests.get(direct_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                total = int(r.headers.get('content-length', 0))
                downloaded = 0

                with open(self.save_path, 'wb') as f:
                    for chunk in r.iter_content(4096):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                percent = int(downloaded * 100 / total)
                                self.progress.emit(percent)
                            else:
                                self.progress.emit(min(95, downloaded // 1024))

            self.progress.emit(100)
            self.finished.emit(self.save_path)

        except Exception as e:
            self.failed.emit(str(e))


class UpdaterWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto Updater")
        self.resize(480, 220)
        self.setStyleSheet("background-color: #f9f9f9;")
        self.state = None
        self.update_info = None

    def showEvent(self, event):
        super().showEvent(event)
        if not self.layout():
            self._init_ui()
        self.check_update()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        label_font = QFont()
        label_font.setPointSize(11)

        self.current_label = QLabel("Current version: —")
        self.current_label.setFont(label_font)

        self.status_label = QLabel("Checking for updates...")
        self.status_label.setFont(label_font)
        self.status_label.setStyleSheet("color: #444;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("0%")
        self.progress_bar.setVisible(False)

        layout.addWidget(self.current_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addStretch()
        self.setLayout(layout)

    def check_update(self):
        self.worker = UpdateWorker()
        self.worker.current_version_fetched.connect(self.update_current_label)
        self.worker.finished.connect(self.on_check_finished)
        self.worker.start()

    def update_current_label(self, ver):
        self.current_label.setText(f"Current version: {ver}")

    def on_check_finished(self, update_info, error):
        if error:
            self.status_label.setText(f"<b style='color:red;'>Error:</b> {error}")
            return

        if not update_info:
            self.status_label.setText("<b style='color:green;'>✓ Up to date</b>")
            return

        self.update_info = update_info
        logical_ver = update_info["version"]
        yandex_link = update_info["link"]

        self.status_label.setText(f"Downloading update v{logical_ver}...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0%")

        zip_name = f"update_v{logical_ver}.zip"
        self.downloader = YandexDownloaderThread(yandex_link, zip_name)
        self.downloader.progress.connect(self.on_progress)
        self.downloader.finished.connect(self.on_zip_downloaded)
        self.downloader.failed.connect(lambda e: self.status_label.setText(f"<b style='color:red;'>Download failed:</b> {e}"))
        self.downloader.start()

    def on_progress(self, percent):
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{percent}%")

    def on_zip_downloaded(self, zip_path):
        logical_ver = self.update_info["version"]
        self.status_label.setText(f"Applying hard-replace update v{logical_ver}...")
        self.apply_hard_update(zip_path, logical_ver)

    def apply_hard_update(self, zip_path, target_version):
        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                # Read metadata
                if 'update_metadata.json' not in zipf.namelist():
                    raise ValueError("update_metadata.json missing in ZIP")

                metadata = json.loads(zipf.read('update_metadata.json'))
                # We ignore metadata['to_version'] — we use target_version from logic

                # --- PHASE 1: Delete files/dirs
                for file in metadata.get('deleted_files', []):
                    fp = (Path.cwd() / file).resolve()
                    if fp.exists():
                        force_remove(str(fp))

                for dir_path in metadata.get('deleted_dirs', []):
                    dp = (Path.cwd() / dir_path).resolve()
                    if dp.exists():
                        force_remove(str(dp))

                # --- PHASE 2: Extract all files
                snapshot_file = None
                for name in zipf.namelist():
                    if name.startswith('snapshot_') and name.endswith('.json'):
                        snapshot_file = name
                        break

                for zip_info in zipf.infolist():
                    if zip_info.filename in ['update_metadata.json', snapshot_file or '']:
                        continue

                    target = (Path.cwd() / zip_info.filename).resolve()
                    if zip_info.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        if target.exists():
                            force_remove(str(target))
                        target.parent.mkdir(parents=True, exist_ok=True)
                        zipf.extract(zip_info, path=Path.cwd())

                # --- PHASE 3: Recreate added dirs
                for dir_path in metadata.get('added_dirs', []):
                    (Path.cwd() / dir_path).mkdir(parents=True, exist_ok=True)

                # --- PHASE 4: SKIP PIP INSTALL (as requested)

                # --- PHASE 5: Update version file to LOGICAL VERSION
                with open(VERSION_FILE, 'w') as f:
                    f.write(str(target_version))

                # Cleanup
                os.remove(zip_path)

                # Success
                self.current_label.setText(f"Current version: {target_version}")
                self.status_label.setText(f"<b style='color:green;'>✅ Update applied: v{target_version}</b>")
                self.progress_bar.setFormat("100%")
                self.progress_bar.setValue(100)

                # Switch view
                if self.state and hasattr(self.state, 'gui') and self.state.gui:
                    self.state.gui.switch_view("custom_view")

        except Exception as e:
            self.status_label.setText(f"<b style='color:red;'>Apply failed:</b> {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = UpdaterWidget()
    widget.show()
    sys.exit(app.exec_())
