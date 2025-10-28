import sys
import os
import json
import zipfile
import shutil
import stat
import requests
import time
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QProgressBar, QApplication, QPushButton, QHBoxLayout
)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QFont

VERSION_FILE = "version"
UPDATE_JSON_URL = "https://raw.githubusercontent.com/Ilya0khiriv/updater_zero/main/pyqt5_vk_uploader_folder/update.json"


def force_remove(path):
    def handle_remove_readonly(func, p, exc_info):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    path = os.path.abspath(path)
    if os.path.isfile(path):
        try:
            os.chmod(path, stat.S_IWRITE)
            os.remove(path)
        except Exception as e:
            print(f"[VERBOSE] Failed to remove file {path}: {e}")
            shutil.rmtree(os.path.dirname(path), onerror=handle_remove_readonly)
    elif os.path.isdir(path):
        shutil.rmtree(path, onerror=handle_remove_readonly)


class UpdateWorker(QThread):
    finished = pyqtSignal(object, str)
    current_version_fetched = pyqtSignal(int)

    def run(self):
        print("[VERBOSE] Starting full update check (fetching all pending versions)...")
        current_version = 0
        try:
            if os.path.exists(VERSION_FILE):
                with open(VERSION_FILE, "r") as f:
                    current_version = int(f.read().strip() or "0")
                print(f"[VERBOSE] Current version: {current_version}")
            else:
                print("[VERBOSE] No version file. Assuming version 0.")
            self.current_version_fetched.emit(current_version)
        except Exception as e:
            print(f"[VERBOSE] Failed to read version: {e}")
            self.finished.emit(None, f"Не удалось прочитать версию: {e}")
            return

        try:
            response = requests.get(UPDATE_JSON_URL.strip(), timeout=10)
            response.raise_for_status()
            version_map = response.json()

            # Get all available version numbers as integers
            available_versions = []
            for v in version_map.keys():
                if v.isdigit():
                    available_versions.append(int(v))
            if not available_versions:
                self.finished.emit([], "")
                return

            latest_version = max(available_versions)
            pending_versions = [v for v in range(current_version + 1, latest_version + 1) if v in available_versions]

            if not pending_versions:
                self.finished.emit([], "")
                return

            updates = []
            for ver in pending_versions:
                ver_str = str(ver)
                yandex_link = version_map[ver_str].strip()
                if not yandex_link or not yandex_link.startswith("http"):
                    self.finished.emit(None, f"Некорректная ссылка для версии {ver}")
                    return
                updates.append({
                    "version": ver,
                    "link": yandex_link
                })

            print(f"[VERBOSE] Pending updates: {[u['version'] for u in updates]}")
            self.finished.emit(updates, "")

        except Exception as e:
            error_msg = f"Ошибка при загрузке списка обновлений: {e}"
            print(f"[VERBOSE] {error_msg}")
            self.finished.emit(None, error_msg)


class YandexDownloaderThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)
    slow_speed_detected = pyqtSignal()

    def __init__(self, yandex_url, save_path):
        super().__init__()
        self.yandex_url = yandex_url
        self.save_path = save_path
        self._last_bytes = 0
        self._last_time = None
        self._slow_counter = 0

    def run(self):
        try:
            api_url = "https://cloud-api.yandex.net/v1/disk/public/resources/download"
            params = {"public_key": self.yandex_url.strip()}
            response = requests.get(api_url, params=params, timeout=10)
            if response.status_code != 200:
                self.failed.emit(f"Yandex API error: {response.status_code}")
                return

            direct_url = response.json().get("href")
            if not direct_url:
                self.failed.emit("Yandex не вернул ссылку для скачивания")
                return

            r = requests.get(direct_url, stream=True, timeout=60)
            r.raise_for_status()

            total = int(r.headers.get('content-length', 0))
            downloaded = 0

            with open(self.save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        now = time.time()
                        if self._last_time is None:
                            self._last_time = now
                            self._last_bytes = downloaded
                        else:
                            elapsed = now - self._last_time
                            if elapsed >= 1.0:
                                bytes_diff = downloaded - self._last_bytes
                                speed_kb_s = (bytes_diff / 1024) / elapsed
                                if speed_kb_s <= 200:
                                    self._slow_counter += 1
                                else:
                                    self._slow_counter = 0

                                if self._slow_counter >= 3:
                                    self.slow_speed_detected.emit()

                                self._last_bytes = downloaded
                                self._last_time = now

                        if total > 0:
                            percent = min(99, int(100 * downloaded / total))
                            self.progress.emit(percent)
                        else:
                            mb = downloaded // (1024 * 1024)
                            self.progress.emit(min(99, max(1, mb)))

            self.progress.emit(100)
            self.finished.emit(self.save_path)

        except Exception as e:
            self.failed.emit(str(e))


class UpdaterWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Автообновление")
        self.resize(480, 300)
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                color: #222222;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            QProgressBar {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                text-align: center;
                color: #444;
                background: #f5f5f5;
            }
            QProgressBar::chunk {
                background-color: #4a90e2;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
        """)
        self.state = None
        self.pending_updates = []
        self.current_update_index = 0
        self.update_info = None
        self.slow_warning_button = None

    def showEvent(self, event):
        super().showEvent(event)
        if self.state:
            self.state.wait = True

        if not self.layout():
            self._init_ui()
        self.check_update()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(16)

        label_font = QFont()
        label_font.setPointSize(12)

        self.current_label = QLabel("Текущая версия: —")
        self.current_label.setFont(label_font)
        self.current_label.setStyleSheet("font-weight: 500;")

        self.status_label = QLabel("Проверка обновлений…")
        self.status_label.setFont(label_font)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #555; padding: 4px 0;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("0%")
        self.progress_bar.setMaximumHeight(20)

        self.slow_warning_button = QPushButton("Закрыть и отключить VPN")
        self.slow_warning_button.setVisible(False)
        self.slow_warning_button.clicked.connect(self.close)
        self.slow_warning_button.setStyleSheet("""
            background-color: #f57c00;
            color: white;
            padding: 6px 16px;
            border-radius: 4px;
            font-weight: bold;
        """)

        layout.addWidget(self.current_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.slow_warning_button)
        layout.addStretch()

        self.setLayout(layout)

    def check_update(self):
        self.worker = UpdateWorker()
        self.worker.current_version_fetched.connect(self.update_current_label)
        self.worker.finished.connect(self.on_check_finished)
        self.worker.start()
        self.status_label.setText("Проверка обновлений…")
        self.progress_bar.setValue(0)

    def update_current_label(self, ver):
        self.current_label.setText(f"Текущая версия: {ver}")

    def on_check_finished(self, update_list, error):
        if error:
            self.status_label.setText(f"<b style='color:#d32f2f;'>Ошибка:</b> {error}")
            return

        if not update_list:
            self.status_label.setText("<b style='color:#388e3c;'>✓ Обновлений нет</b>")
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("100%")

            if self.state:
                self.state.wait = False
            else:
                exit()
            return

        self.pending_updates = update_list
        self.current_update_index = 0
        self.apply_next_update()

    def apply_next_update(self):
        if self.current_update_index >= len(self.pending_updates):
            final_ver = self.pending_updates[-1]["version"]
            self.current_label.setText(f"Текущая версия: {final_ver}")
            self.status_label.setText(f"<b style='color:#388e3c;'>✅ Все обновления применены (v{final_ver})</b>")
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("100%")
            if self.state:
                self.state.wait = False
            else:
                exit()
            return

        self.update_info = self.pending_updates[self.current_update_index]
        self.start_download()

    def start_download(self):
        logical_ver = self.update_info["version"]
        yandex_link = self.update_info["link"]

        self.status_label.setText(f"Загрузка обновления v{logical_ver}…")
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0%")
        self.slow_warning_button.setVisible(False)

        zip_name = f"update_v{logical_ver}.zip"
        self.downloader = YandexDownloaderThread(yandex_link, zip_name)
        self.downloader.progress.connect(self.on_progress)
        self.downloader.finished.connect(self.on_zip_downloaded)
        self.downloader.failed.connect(
            lambda e: self.status_label.setText(f"<b style='color:#d32f2f;'>Ошибка загрузки v{self.update_info['version']}:</b> {e}")
        )
        self.downloader.slow_speed_detected.connect(self.on_slow_speed_detected)
        self.downloader.start()

    def on_slow_speed_detected(self):
        self.status_label.setText(
            "<b style='color:#e65100;'>⚠️ Скачивание очень медленное (≤200 КБ/с)</b><br>"
            "Возможно, включён VPN. Отключите его и перезапустите обновление."
        )
        self.slow_warning_button.setVisible(True)

    def on_progress(self, percent):
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{percent}%")

    def on_zip_downloaded(self, zip_path):
        logical_ver = self.update_info["version"]
        self.status_label.setText(f"Применение обновления v{logical_ver}…")
        self.apply_hard_update(zip_path, logical_ver)

    def apply_hard_update(self, zip_path, target_version):
        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                if 'update_metadata.json' not in zipf.namelist():
                    raise ValueError("Файл update_metadata.json отсутствует в архиве")

                metadata = json.loads(zipf.read('update_metadata.json'))

                for file in metadata.get('deleted_files', []):
                    fp = (Path.cwd() / file).resolve()
                    if fp.exists():
                        force_remove(str(fp))

                for dir_path in metadata.get('deleted_dirs', []):
                    dp = (Path.cwd() / dir_path).resolve()
                    if dp.exists():
                        force_remove(str(dp))

                snapshot_file = next(
                    (name for name in zipf.namelist() if name.startswith('snapshot_') and name.endswith('.json')),
                    None
                )

                for zip_info in zipf.infolist():
                    if zip_info.filename in ['update_metadata.json', snapshot_file or '']:
                        continue
                    target = (Path.cwd() / zip_info.filename).resolve()
                    if not zip_info.is_dir():
                        if target.exists():
                            force_remove(str(target))
                        target.parent.mkdir(parents=True, exist_ok=True)
                        zipf.extract(zip_info, path=Path.cwd())

                for dir_path in metadata.get('added_dirs', []):
                    (Path.cwd() / dir_path).mkdir(parents=True, exist_ok=True)

                with open(VERSION_FILE, 'w') as f:
                    f.write(str(target_version))

                os.remove(zip_path)

                # Proceed to next update
                self.current_update_index += 1
                self.apply_next_update()

        except Exception as e:
            self.status_label.setText(f"<b style='color:#d32f2f;'>Ошибка применения v{target_version}:</b> {str(e)}")
            print(f"[VERBOSE] Update apply error: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = UpdaterWidget()
    widget.show()
    sys.exit(app.exec_())
