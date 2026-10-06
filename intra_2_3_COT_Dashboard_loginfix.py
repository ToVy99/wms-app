import sys
import os
import time
import math
import json
import pandas as pd
import re
import urllib.request
import urllib.error
import urllib.parse
import subprocess
from datetime import datetime, timedelta, timezone

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QListWidget,
    QTableView, QFileDialog, QMessageBox, QVBoxLayout, QHBoxLayout,
    QLineEdit, QHeaderView, QCheckBox, QComboBox, QFrame, QProgressDialog,
    QTabWidget, QButtonGroup, QDateEdit
)

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QEvent, QAbstractTableModel, QModelIndex, QDate
from PySide6.QtGui import QStandardItemModel, QStandardItem, QKeySequence, QShortcut, QCursor, QMovie, QColor, QPalette

# --- PLAYWRIGHT: vận chuyển WMS qua Chrome (xem chrome_cot.py) ---
from playwright.sync_api import sync_playwright

# --- TÍCH HỢP MATPLOTLIB VÀO PYSIDE6 ---
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# ================= CẤU HÌNH PHIÊN BẢN & AUTO-UPDATE =================
CURRENT_VERSION = "2.4.3_Chrome_Native14"
def _config_file_path():
    if not getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "wms_config.json")
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "IntraCity", "wms_config.json")


CONFIG_FILE = _config_file_path()
if getattr(sys, "frozen", False):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
VERSION_URL = "https://raw.githubusercontent.com/ToVy99/wms-app/main/version.json"

ALLOWED_COLUMNS = [
    "Shopee order SN", "WMS Order No", "Status", "WHS ID", "Wave Type",
    "SKU Name", "Category", "Picking ID", "Device ID", "LM Tracking Number",
    "3PL", "New 3PL", "Buyer Name", "Buyer State", "Buyer City",
    "Buyer Addr", "Buyer Email", "Picked By", "Sorted By", "Checked By",
    "Packed by", "Shipped By", "Cut-Off Time"
]

# ================= CSS GIAO DIỆN HIỆN ĐẠI (DARK MODERN THEME) =================
MODERN_STYLE = """
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

/* --- BUTTONS --- */
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #45475a;
    border-color: #585b70;
}
QPushButton:pressed {
    background-color: #585b70;
}

/* API COT BUTTONS */
QPushButton.cotBtn {
    background-color: #181825;
    color: #89b4fa;
    border: 1px solid #89b4fa;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
    font-weight: bold;
}
QPushButton.cotBtn:hover {
    background-color: #89b4fa;
    color: #11111b;
}

QPushButton[cotChoice="true"]:checked, QPushButton[cotMetric="true"]:checked {
    background-color: #89b4fa;
    color: #11111b;
    border: 1px solid #89b4fa;
}
QPushButton[cotChoice="true"] { padding: 8px 12px; }
QPushButton[cotMetric="true"] { padding: 6px 8px; }

/* Nút đặc biệt */
QPushButton#btnLoginWMS {
    background-color: #ff6600;
    color: #ffffff;
    border: none;
    font-weight: bold;
}
QPushButton#btnLoginWMS:hover {
    background-color: #e65c00;
}

QPushButton#btnBasket {
    background-color: #00b4d8;
    color: #ffffff;
    border: none;
}
QPushButton#btnBasket:hover {
    background-color: #0096c7;
}

QPushButton#btnSave {
    background-color: #2ec4b6;
    color: #ffffff;
    border: none;
}
QPushButton#btnSave:hover {
    background-color: #20a39e;
}

/* --- INPUT & COMBOBOX --- */
QLineEdit {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 5px 10px;
}
QLineEdit:focus {
    border: 1px solid #89b4fa;
}

QComboBox {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 5px 10px;
}

/* --- LIST WIDGET --- */
QListWidget {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 8px;
    padding: 5px;
}
QListWidget::item {
    padding: 6px;
    border-radius: 4px;
}
QListWidget::item:hover {
    background-color: #313244;
}
QListWidget::item:selected {
    background-color: #89b4fa;
    color: #11111b;
    font-weight: bold;
}

/* --- TABLE VIEW --- */
QTableView {
    background-color: #181825;
    gridline-color: #313244;
    border: 1px solid #313244;
    border-radius: 8px;
    selection-background-color: #45475a;
    selection-color: #ffffff;
}
QHeaderView::section {
    background-color: #11111b;
    color: #a6adc8;
    padding: 6px;
    border: none;
    font-weight: bold;
}

/* --- TAB WIDGET --- */
QTabWidget::pane {
    border: 1px solid #313244;
    border-radius: 8px;
    background-color: #181825;
}
QTabBar::tab {
    background-color: #181825;
    color: #a6adc8;
    padding: 6px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #313244;
    color: #89b4fa;
    font-weight: bold;
}

/* --- KPI CARDS & STATUS BAR --- */
QFrame.kpiCard {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 8px;
    padding: 8px;
}
QFrame#bottomStatusBar {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 4px 8px;
}
"""

from chrome_cot import ChromeCotTab

# ================= TÍNH NĂNG TỰ ĐỘNG CẬP NHẬT =================
class AutoUpdaterThread(QThread):
    update_available = Signal(dict)

    def run(self):
        try:
            no_cache_url = f"{VERSION_URL}?t={int(time.time())}"
            req = urllib.request.Request(no_cache_url, headers={'User-Agent': 'Mozilla/5.0', 'Cache-Control': 'no-cache'})
            
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                server_version = data.get("version", "1.0.0")
                
                if self._is_newer_version(server_version, CURRENT_VERSION):
                    self.update_available.emit(data)
        except Exception:
            pass

    def _is_newer_version(self, latest_str, current_str):
        def clean_and_parse(v_str):
            cleaned = re.sub(r'[^\d.]', '', str(v_str))
            return [int(x) for x in cleaned.split('.') if x.isdigit()]
        
        try:
            return clean_and_parse(latest_str) > clean_and_parse(current_str)
        except Exception:
            return False


# ================= WIDGET BIỂU ĐỒ TỰ ĐỘNG THÍCH ỨNG THEME =================
class ChartCanvas(FigureCanvas):
    def __init__(self, parent=None):
        fig = Figure(figsize=(4.5, 2.8))
        self.axes = fig.add_subplot(111)
        fig.subplots_adjust(left=0.02, right=0.58, top=0.90, bottom=0.08)
        super().__init__(fig)
        self.setParent(parent)
        self.apply_theme_colors()

    def apply_theme_colors(self):
        bg_color = "#181825"
        self.text_color = "#cdd6f4"
        self.figure.set_facecolor(bg_color)
        self.axes.set_facecolor(bg_color)

    def plot_pie(self, series_data, title_text=""):
        self.apply_theme_colors()
        self.axes.clear()
        
        if series_data.empty:
            self.axes.text(
                0.5, 0.5, 'Chưa có dữ liệu', 
                color=self.text_color, ha='center', va='center'
            )
            self.axes.axis('off')
            self.draw()
            return

        top_n = 5
        if len(series_data) > top_n:
            top_series = series_data.iloc[:top_n].copy()
            other_sum = series_data.iloc[top_n:].sum()
            top_series["Khác"] = other_sum
            series_data = top_series

        labels = series_data.index
        values = series_data.values
        colors = ['#89b4fa', '#f38ba8', '#f9e2af', '#a6e3a1', '#cba6f7', '#fab387']

        def my_autopct(pct):
            return f'{pct:.1f}%' if pct >= 3.0 else ''

        wedges, texts, autotexts = self.axes.pie(
            values, 
            labels=None, 
            autopct=my_autopct, 
            startangle=140,
            colors=colors[:len(values)],
            pctdistance=0.68,
            radius=1.1
        )

        for autotext in autotexts:
            autotext.set_color('#11111b')
            autotext.set_weight('bold')
            autotext.set_fontsize(8)

        self.axes.legend(
            wedges, labels,
            loc="center left",
            bbox_to_anchor=(1, 0.5),
            fontsize=8.5,
            frameon=False,
            labelcolor=self.text_color
        )

        if title_text:
            self.axes.set_title(
                title_text, 
                color=self.text_color, 
                fontsize=9, 
                fontweight='bold', 
                loc='left', 
                pad=6
            )
            
        self.axes.axis('equal')
        self.draw()


# ================= MODEL BẢNG HIỂN THỊ SIÊU NHANH =================
class PandasModel(QAbstractTableModel):
    def __init__(self, data=pd.DataFrame(), search_keyword=""):
        super().__init__()
        self._data = data
        self._search_keyword = search_keyword.lower()

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._data.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        value = self._data.iat[row, col]

        if role == Qt.DisplayRole:
            return "" if pd.isna(value) else str(value)
        elif role == Qt.BackgroundRole and self._search_keyword:
            val_str = "" if pd.isna(value) else str(value).lower()
            if self._search_keyword in val_str:
                return QColor(243, 139, 168, 180)
        elif role == Qt.ForegroundRole and self._search_keyword:
            val_str = "" if pd.isna(value) else str(value).lower()
            if self._search_keyword in val_str:
                return QColor(255, 255, 255)

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._data.columns[section])
            elif orientation == Qt.Vertical:
                return str(section + 1)
        return None

    def update_data(self, new_data, search_keyword=""):
        self.beginResetModel()
        self._data = new_data
        self._search_keyword = search_keyword.lower()
        self.endResetModel()


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "default_3pl": ["SPX Express", "SPX Express NDD - Trong Ngày"],
        "default_buyer_state": ["Hà Nội", "Thành phố Hà Nội"],
        "wms_cookie": ""
    }


def save_config(config_data):
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        temp_file = CONFIG_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        os.replace(temp_file, CONFIG_FILE)
        return True
    except Exception:
        return False


class CheckableComboBox(QComboBox):
    checkedItemsChanged = Signal()

    def __init__(self, placeholder="Tất cả", parent=None):
        super().__init__(parent)
        self.placeholder = placeholder
        self.setModel(QStandardItemModel(self))
        
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setCursor(QCursor(Qt.PointingHandCursor))
        
        self.view().setCursor(QCursor(Qt.PointingHandCursor))
        self.view().pressed.connect(self._on_item_pressed)
        
        self._is_updating_select_all = False

    def populate_items(self, items, default_selected=None):
        model = self.model()
        old_model_block = model.blockSignals(True)
        old_combo_block = self.blockSignals(True)
        try:
            model.clear()

            if default_selected is None:
                default_selected = []

            item_all = QStandardItem("-- Chọn tất cả --")
            item_all.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item_all.setData("SELECT_ALL", Qt.UserRole)
            item_all.setCheckState(Qt.Unchecked)
            model.appendRow(item_all)

            valid_items = []
            all_checked = True
            for text in items:
                text_str = str(text).strip()
                if not text_str or text_str.lower() == "nan":
                    continue

                valid_items.append(text_str)
                item = QStandardItem(text_str)
                item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)

                if text_str in default_selected:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
                    all_checked = False

                model.appendRow(item)

            if valid_items and all_checked:
                item_all.setCheckState(Qt.Checked)

            self.update_text()
        finally:
            self.blockSignals(old_combo_block)
            model.blockSignals(old_model_block)

    def _on_item_pressed(self, index):
        model = self.model()
        item = model.itemFromIndex(index)
        if not item:
            return

        # Chặn dataChanged tạm thời để một lần click chỉ lọc đúng 1 lần,
        # đặc biệt khi dùng "Chọn tất cả".
        old_block = model.blockSignals(True)
        try:
            new_state = Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
            item.setCheckState(new_state)

            if item.data(Qt.UserRole) == "SELECT_ALL":
                self._toggle_select_all(new_state)
            else:
                self._sync_select_all_state()

            self.update_text()
        finally:
            model.blockSignals(old_block)

        self.checkedItemsChanged.emit()

    def _toggle_select_all(self, state):
        self._is_updating_select_all = True
        try:
            model = self.model()
            for i in range(1, model.rowCount()):
                item = model.item(i)
                if item:
                    item.setCheckState(state)
        finally:
            self._is_updating_select_all = False

    def _sync_select_all_state(self):
        if self._is_updating_select_all:
            return
            
        model = self.model()
        item_all = model.item(0)
        if not item_all or item_all.data(Qt.UserRole) != "SELECT_ALL":
            return

        all_checked = True
        for i in range(1, model.rowCount()):
            item = model.item(i)
            if item and item.checkState() == Qt.Unchecked:
                all_checked = False
                break

        item_all.setCheckState(Qt.Checked if all_checked else Qt.Unchecked)

    def update_text(self):
        checked = self.get_checked_items()
        model = self.model()
        total_data_items = model.rowCount() - 1 if model.rowCount() > 0 else 0

        if not checked:
            self.lineEdit().setText(f"-- {self.placeholder} (Chưa chọn) --")
        elif len(checked) == total_data_items and total_data_items > 0:
            self.lineEdit().setText(f"-- {self.placeholder} (Tất cả) --")
        else:
            self.lineEdit().setText(", ".join(checked))

    def get_checked_items(self):
        checked = []
        model = self.model()
        for i in range(1, model.rowCount()):
            item = model.item(i)
            if item and item.checkState() == Qt.Checked:
                checked.append(item.text())
        return checked


class DownloadWatcherHandler(FileSystemEventHandler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def _process_file(self, filepath):
        filename = os.path.basename(filepath)
        ext = os.path.splitext(filepath)[1].lower()

        if ext not in ['.xlsx', '.xls']:
            return
        if filename.startswith('~$') or filename.endswith('.crdownload') or filename.endswith('.tmp'):
            return

        # Chờ file ghi xong: kích thước + mtime phải ổn định liên tiếp.
        # Việc chỉ đọc thử 100 byte không đảm bảo Chrome/Excel đã ghi xong file.
        last_signature = None
        stable_checks = 0
        for _ in range(40):
            if not os.path.exists(filepath):
                return
            try:
                stat = os.stat(filepath)
                signature = (stat.st_size, stat.st_mtime_ns)

                if stat.st_size > 0 and signature == last_signature:
                    stable_checks += 1
                else:
                    stable_checks = 0
                    last_signature = signature

                if stable_checks >= 4:
                    with open(filepath, 'rb') as f:
                        f.read(512)
                    self.callback(filepath)
                    return
            except (PermissionError, OSError):
                stable_checks = 0

            time.sleep(0.3)

    def on_created(self, event):
        if not event.is_directory:
            self._process_file(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._process_file(event.dest_path)


class WatcherThread(QThread):
    file_detected = Signal(str)

    def __init__(self, watch_path):
        super().__init__()
        self.watch_path = os.path.realpath(watch_path)
        self.observer = None

    def run(self):
        event_handler = DownloadWatcherHandler(self._on_file_found)
        self.observer = Observer()
        try:
            self.observer.schedule(event_handler, path=self.watch_path, recursive=False)
            self.observer.start()

            while not self.isInterruptionRequested():
                time.sleep(0.2)
        finally:
            if self.observer:
                try:
                    self.observer.stop()
                    self.observer.join(timeout=2)
                except Exception:
                    pass

    def _on_file_found(self, filepath):
        if not self.isInterruptionRequested():
            self.file_detected.emit(filepath)

    def stop(self):
        self.requestInterruption()
        if self.observer:
            try:
                self.observer.stop()
            except Exception:
                pass
        self.wait(3000)


class DataLoaderThread(QThread):
    data_loaded = Signal(object)
    error = Signal(str)

    def __init__(self, mode, source=None):
        super().__init__()
        self.mode = mode
        self.source = source

    def run(self):
        try:
            if self.mode == 'excel':
                df = self._smart_read_excel(self.source)
            elif self.mode == 'clipboard':
                df = pd.read_clipboard(sep="\t")
            else:
                df = pd.DataFrame()

            if not df.empty:
                for col in df.columns:
                    if 'picking' in str(col).lower() and 'id' in str(col).lower():
                        def clean_picking_id(val):
                            if pd.isna(val):
                                return ""
                            s = str(val).strip()
                            if s.endswith('.0'):
                                s = s[:-2]
                            return s
                        df[col] = df[col].apply(clean_picking_id)

            self.data_loaded.emit(df)
        except Exception as e:
            self.error.emit(str(e))

    def _smart_read_excel(self, filepath):
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            raise ValueError("Tệp tin rỗng (0 KB) hoặc không tồn tại.")

        try:
            return pd.read_excel(filepath, engine='calamine')
        except Exception:
            pass

        try:
            return pd.read_excel(filepath, engine='openpyxl')
        except Exception:
            pass

        try:
            return pd.read_excel(filepath, engine='xlrd')
        except Exception:
            pass

        try:
            dfs = pd.read_html(filepath)
            if dfs:
                return dfs[0]
        except Exception:
            pass

        try:
            return pd.read_csv(filepath, sep=None, engine='python')
        except Exception:
            pass

        raise ValueError("Không thể nhận diện định dạng file Excel. Vui lòng kiểm tra lại file đã tải.")


class WMSDashboard(QWidget):

    def __init__(self):
        super().__init__()

        # ===== Dữ liệu Excel hiện có =====
        self.df = pd.DataFrame()
        self.filtered = pd.DataFrame()
        self.wave_df = pd.DataFrame()
        self.current_scope_df = pd.DataFrame()

        self.current_status = ""
        self.current_watch_path = ""
        self.start_time = None
        self.dots_count = 0
        self.loader_thread = None
        self._loader_started_at = None
        self._active_load = None
        self._pending_load = None

        self.config = load_config()

        self.setWindowTitle(f"IntraCity v{CURRENT_VERSION}")
        self.resize(1680, 950)
        self.setStyleSheet(MODERN_STYLE)

        self.table_model = PandasModel()

        self.build_ui()
        self.start_folder_watcher()
        self.check_for_updates()

    def check_for_updates(self):
        self.updater_thread = AutoUpdaterThread()
        self.updater_thread.update_available.connect(self.prompt_update)
        self.updater_thread.start()

    def prompt_update(self, update_info):
        new_version = update_info.get("version", "Mới")
        download_url = update_info.get("download_url", "")
        changelog = update_info.get("changelog", "Cập nhật hệ thống.")

        msg = f"Đã có phiên bản mới: v{new_version}\n\nNội dung nâng cấp:\n{changelog}\n\nBạn có muốn cập nhật ngay không?"
        reply = QMessageBox.question(self, "Phát hiện bản cập nhật mới", msg, QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes and download_url:
            self.download_and_install_update(download_url)

    def download_and_install_update(self, download_url):
        # Không bao giờ ghi đè sys.executable khi đang chạy bằng Python source.
        if not getattr(sys, "frozen", False):
            QMessageBox.warning(
                self,
                "Không thể tự cập nhật",
                "Tự cập nhật chỉ hoạt động trên bản EXE đã đóng gói. "
                "Bản chạy bằng Python source sẽ không bị sửa/ghi đè."
            )
            return

        if not str(download_url).lower().startswith("https://"):
            QMessageBox.warning(self, "Lỗi cập nhật", "Link cập nhật phải sử dụng HTTPS.")
            return

        current_exe = os.path.realpath(sys.executable)
        temp_exe = current_exe + ".download"
        backup_exe = current_exe + ".old"

        try:
            progress = QProgressDialog("Đang tải bản cập nhật...", "Hủy", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()

            if os.path.exists(temp_exe):
                try:
                    os.remove(temp_exe)
                except OSError:
                    pass

            def report(blocknum, blocksize, totalsize):
                if progress.wasCanceled():
                    raise RuntimeError("Đã hủy cập nhật.")
                if totalsize > 0:
                    readsofar = blocknum * blocksize
                    percent = min(100, int(readsofar * 100 / totalsize))
                    progress.setValue(percent)
                    QApplication.processEvents()

            # Tải sang file tạm trước. EXE hiện tại vẫn nguyên vẹn nếu download lỗi.
            urllib.request.urlretrieve(download_url, temp_exe, reporthook=report)

            if not os.path.exists(temp_exe) or os.path.getsize(temp_exe) == 0:
                raise RuntimeError("File cập nhật tải về rỗng hoặc không tồn tại.")

            progress.setValue(100)

            bat_file = os.path.join(os.path.dirname(current_exe), "apply_update.bat")
            bat_script = f"""@echo off
chcp 65001 > nul
setlocal

:wait_app
move /Y "{current_exe}" "{backup_exe}" >nul 2>&1
if exist "{current_exe}" (
    timeout /t 1 /nobreak >nul
    goto wait_app
)

move /Y "{temp_exe}" "{current_exe}" >nul 2>&1
if not exist "{current_exe}" (
    move /Y "{backup_exe}" "{current_exe}" >nul 2>&1
    exit /b 1
)

start "" "{current_exe}"
timeout /t 3 /nobreak >nul
del /F /Q "{backup_exe}" >nul 2>&1
(goto) 2>nul & del "%~f0"
"""
            with open(bat_file, "w", encoding="utf-8") as f:
                f.write(bat_script)

            QMessageBox.information(self, "Cập nhật", "Đã tải xong! Ứng dụng sẽ tự khởi động lại.")
            subprocess.Popen([bat_file], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            QApplication.quit()

        except Exception as e:
            if os.path.exists(temp_exe):
                try:
                    os.remove(temp_exe)
                except OSError:
                    pass
            QMessageBox.warning(self, "Lỗi cập nhật", f"Không thể hoàn tất cập nhật: {str(e)}")

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        # ===== Thanh WMS dùng chung =====
        global_top = QHBoxLayout()

        self.btnLoginWMS = QPushButton("🔑 Đăng nhập WMS")
        self.btnLoginWMS.setObjectName("btnLoginWMS")
        self.lblWMSState = QLabel(
            "⚪ Chưa kết nối Chrome WMS"
        )
        self.lblWMSState.setStyleSheet("color: #a6adc8; font-weight: 600;")

        global_top.addWidget(self.btnLoginWMS)
        global_top.addWidget(self.lblWMSState)
        global_top.addStretch()
        root.addLayout(global_top)

        # ===== Banner trạng thái dùng chung =====
        status_layout = QHBoxLayout()
        self.statusBanner = QFrame()
        self.statusBanner.setFrameShape(QFrame.StyledPanel)
        banner_inner = QHBoxLayout(self.statusBanner)
        banner_inner.setContentsMargins(10, 4, 10, 4)

        self.lblGifIcon = QLabel()
        self.lblStatusMsg = QLabel("Sẵn sàng làm việc!")

        self.statusBanner.setStyleSheet("background-color: #313244; border-radius: 6px;")
        self.lblStatusMsg.setStyleSheet("font-size: 13px; font-weight: bold; color: #cdd6f4;")

        banner_inner.addWidget(self.lblGifIcon)
        banner_inner.addWidget(self.lblStatusMsg)
        status_layout.addWidget(self.statusBanner)
        status_layout.addStretch()
        root.addLayout(status_layout)

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._update_loading_animation)

        if os.path.exists("loading.gif"):
            self.movie = QMovie("loading.gif")
            self.lblGifIcon.setMovie(self.movie)

        # ===== Tabs chính =====
        self.mainTabs = QTabWidget()
        root.addWidget(self.mainTabs, 1)

        # ==============================================================
        # TAB 1: COT DASHBOARD
        # ==============================================================
        self.cotTab = ChromeCotTab(self.config, save_config, self)
        self.cotTab.bridge.sessionChanged.connect(self._chrome_session_changed)
        self.mainTabs.addTab(self.cotTab, "⚡ COT")

        # ==============================================================
        # TAB 2: DASHBOARD EXCEL HIỆN CÓ
        # ==============================================================
        self.excelTab = QWidget()
        excel_root = QVBoxLayout(self.excelTab)
        excel_root.setContentsMargins(8, 8, 8, 8)
        excel_root.setSpacing(10)

        top = QHBoxLayout()

        self.btnClipboard = QPushButton("📋 Đọc Clipboard")
        self.btnExcel = QPushButton("📂 Mở Excel")
        self.btnCopyTable = QPushButton("📄 Copy Bảng")
        self.btnRefresh = QPushButton("🔄 Refresh")
        self.btnExport = QPushButton("📤 Export File")

        self.btnBasketOrders = QPushButton("🧺 Đơn hàng dùng mã rổ")
        self.btnBasketOrders.setObjectName("btnBasket")

        self.btnSelectFolder = QPushButton("📁 Chọn thư mục theo dõi")
        self.chkAutoWatch = QCheckBox("👀 Tự đọc file mới")
        self.chkAutoWatch.setChecked(True)

        self.searchBox = QLineEdit()
        self.searchBox.setPlaceholderText("🔍 Tìm Kiếm...")
        self.searchBox.setMinimumWidth(220)

        top.addWidget(self.btnClipboard)
        top.addWidget(self.btnExcel)
        top.addWidget(self.btnCopyTable)
        top.addWidget(self.btnRefresh)
        top.addWidget(self.btnExport)
        top.addWidget(self.btnBasketOrders)
        top.addSpacing(10)
        top.addWidget(self.btnSelectFolder)
        top.addWidget(self.chkAutoWatch)
        top.addStretch()
        top.addWidget(self.searchBox)
        excel_root.addLayout(top)

        filter_bar = QHBoxLayout()

        filter_bar.addWidget(QLabel("🚚 New 3PL:"))
        self.combo3PL = CheckableComboBox("New 3PL")
        self.combo3PL.setMinimumWidth(320)
        self.combo3PL.setMaximumWidth(400)
        filter_bar.addWidget(self.combo3PL)

        filter_bar.addSpacing(15)
        filter_bar.addWidget(QLabel("📍 Buyer State:"))
        self.comboState = CheckableComboBox("Buyer State")
        self.comboState.setMinimumWidth(350)
        filter_bar.addWidget(self.comboState)

        filter_bar.addSpacing(15)
        self.btnSaveDefault = QPushButton("📌 Lưu làm mặc định")
        self.btnSaveDefault.setObjectName("btnSave")
        filter_bar.addWidget(self.btnSaveDefault)
        filter_bar.addStretch()
        excel_root.addLayout(filter_bar)

        kpi = QHBoxLayout()

        def create_kpi_card(title, initial_val, color):
            frame = QFrame()
            frame.setProperty("class", "kpiCard")
            lay = QVBoxLayout(frame)
            lay.setContentsMargins(12, 6, 12, 6)
            lay.setSpacing(2)

            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("font-size: 11px; color: #a6adc8; font-weight: 600;")

            lbl_val = QLabel(initial_val)
            lbl_val.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {color};")

            lay.addWidget(lbl_title)
            lay.addWidget(lbl_val)
            return frame, lbl_val

        card1, self.lblTotal = create_kpi_card("TỔNG ĐƠN HÀNG", "0", "#89b4fa")
        card2, self.lblOutbound = create_kpi_card("ĐƠN OUTBOUND", "0", "#f9e2af")
        card3, self.lblPercent = create_kpi_card("TỶ LỆ OUTBOUND", "0.00%", "#a6e3a1")
        card4, self.lblTimer = create_kpi_card("THỜI GIAN XỬ LÝ", "0.00s", "#cba6f7")

        kpi.addWidget(card1)
        kpi.addWidget(card2)
        kpi.addWidget(card3)
        kpi.addWidget(card4)
        kpi.addStretch()
        excel_root.addLayout(kpi)

        body = QHBoxLayout()

        left_side_layout = QVBoxLayout()
        left_side_layout.setContentsMargins(0, 0, 0, 0)

        top_lists_layout = QHBoxLayout()

        self.statusList = QListWidget()
        self.statusList.setFixedWidth(210)
        self.waveList = QListWidget()
        self.waveList.setFixedWidth(230)

        top_lists_layout.addWidget(self.statusList)
        top_lists_layout.addWidget(self.waveList)

        self.chartTabs = QTabWidget()
        self.chartTabs.setFixedWidth(445)

        self.chartWaveCanvas = ChartCanvas(self)
        self.chartCategoryCanvas = ChartCanvas(self)

        self.perfWidget = QWidget()
        perf_layout = QVBoxLayout(self.perfWidget)
        perf_layout.setContentsMargins(4, 4, 4, 4)

        self.perfList = QListWidget()
        perf_layout.addWidget(QLabel("🏆 Top Nhân Viên Nhặt/Đóng hàng:"))
        perf_layout.addWidget(self.perfList)

        self.chartTabs.addTab(self.chartWaveCanvas, "Wave Type")
        self.chartTabs.addTab(self.chartCategoryCanvas, "Category")
        self.chartTabs.addTab(self.perfWidget, "Năng suất")

        self.lblAuthor = QLabel("✍ Tác giả: Đô Rê Mon")
        self.lblAuthor.setStyleSheet(
            "font-size: 11px; color: #585b70; font-weight: bold; margin-top: 3px;"
        )

        left_side_layout.addLayout(top_lists_layout, 1)
        left_side_layout.addWidget(self.chartTabs, 1)
        left_side_layout.addWidget(self.lblAuthor)

        table_container = QVBoxLayout()
        table_container.setSpacing(6)

        self.table = QTableView()
        self.table.setModel(self.table_model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table_container.addWidget(self.table, 1)

        self.bottomStatusBar = QFrame()
        self.bottomStatusBar.setObjectName("bottomStatusBar")
        bottom_lay = QHBoxLayout(self.bottomStatusBar)
        bottom_lay.setContentsMargins(8, 4, 8, 4)

        self.lblRowCount = QLabel("📊 Tổng dòng: 0 | Đã chọn: 0")
        self.lblSelectedDetail = QLabel("💡 Chi tiết đơn: Click vào dòng để xem")
        self.lblRowCount.setStyleSheet("color: #89b4fa; font-weight: bold;")
        self.lblSelectedDetail.setStyleSheet("color: #a6adc8;")

        bottom_lay.addWidget(self.lblRowCount)
        bottom_lay.addSpacing(20)
        bottom_lay.addWidget(self.lblSelectedDetail)
        bottom_lay.addStretch()
        table_container.addWidget(self.bottomStatusBar)

        body.addLayout(left_side_layout)
        body.addLayout(table_container, 1)
        excel_root.addLayout(body, 1)

        self.mainTabs.addTab(self.excelTab, "📊 Excel / Outbound")

        self.btnLoginWMS.clicked.connect(self.cotTab.bridge.connect_chrome)

        # ===== Signal Excel hiện có =====
        self.btnClipboard.clicked.connect(self.load_clipboard)
        self.btnExcel.clicked.connect(self.load_excel)
        self.btnCopyTable.clicked.connect(lambda: self.copy_table_to_clipboard(selection_only=False))
        self.btnRefresh.clicked.connect(self.refresh)
        self.btnExport.clicked.connect(self.export_excel)
        self.btnSelectFolder.clicked.connect(self.select_watch_folder)

        self.searchBox.textChanged.connect(self.search_order)
        self.statusList.clicked.connect(self.click_status)
        self.waveList.clicked.connect(self.click_wave)
        self.btnBasketOrders.clicked.connect(self.filter_basket_orders)

        self.combo3PL.checkedItemsChanged.connect(self._on_filter_changed)
        self.comboState.checkedItemsChanged.connect(self._on_filter_changed)
        self.btnSaveDefault.clicked.connect(self.save_defaults)

        self.table.selectionModel().selectionChanged.connect(self.update_bottom_status_bar)
        self.table.clicked.connect(self.on_table_row_clicked)

        shortcut_copy = QShortcut(QKeySequence.Copy, self.table)
        shortcut_copy.activated.connect(lambda: self.copy_table_to_clipboard(selection_only=True))

        shortcut_select_all = QShortcut(QKeySequence.SelectAll, self.table)
        shortcut_select_all.activated.connect(self.table.selectAll)

    def _chrome_session_changed(self, connected, message):
        self.lblWMSState.setText("🟢 Chrome WMS đang mở" if connected else "⚪ Chrome WMS chưa kết nối")
        self.set_banner_status(False, success=connected, custom_msg=message)

    def update_bottom_status_bar(self):
        df = self.table_model._data
        total_rows = len(df)
        
        selected_indexes = self.table.selectedIndexes()
        if selected_indexes:
            selected_rows = len(set(idx.row() for idx in selected_indexes))
        else:
            selected_rows = 0

        self.lblRowCount.setText(f"📊 Hiển thị: {total_rows:,} dòng | Đã chọn: {selected_rows:,} dòng")

    def on_table_row_clicked(self, index):
        if not index.isValid():
            return
        
        row = index.row()
        df = self.table_model._data
        if row >= len(df):
            return

        row_data = df.iloc[row]
        
        buyer = str(row_data.get("Buyer Name", "N/A"))
        state = str(row_data.get("Buyer State", "N/A"))
        picker = str(row_data.get("Picked By", "N/A"))
        
        self.lblSelectedDetail.setText(f"💡 Đơn: {buyer} | Tỉnh: {state} | Picked by: {picker}")

    def update_performance_tab(self, df):
        self.perfList.clear()
        if df.empty:
            return

        if "Picked By" in df.columns:
            picked_counts = df["Picked By"].dropna().value_counts().head(5)
            if not picked_counts.empty:
                self.perfList.addItem("--- TOP PICKERS (Nhặt hàng) ---")
                for name, count in picked_counts.items():
                    if str(name).strip():
                        self.perfList.addItem(f"🛒 {name}: {count:,} đơn")

        if "Sorted By" in df.columns:
            sorted_counts = df["Sorted By"].dropna().value_counts().head(5)
            if not sorted_counts.empty:
                self.perfList.addItem("--- TOP SORTERS (Phân loại) ---")
                for name, count in sorted_counts.items():
                    if str(name).strip():
                        self.perfList.addItem(f"🗂 {name}: {count:,} đơn")

        if "Checked By" in df.columns:
            checked_counts = df["Checked By"].dropna().value_counts().head(5)
            if not checked_counts.empty:
                self.perfList.addItem("--- TOP CHECKERS (Kiểm hàng) ---")
                for name, count in checked_counts.items():
                    if str(name).strip():
                        self.perfList.addItem(f"🔍 {name}: {count:,} đơn")

        if "Packed by" in df.columns:
            packed_counts = df["Packed by"].dropna().value_counts().head(5)
            if not packed_counts.empty:
                self.perfList.addItem("--- TOP PACKERS (Đóng gói) ---")
                for name, count in packed_counts.items():
                    if str(name).strip():
                        self.perfList.addItem(f"📦 {name}: {count:,} đơn")

    def set_banner_status(self, is_loading=False, success=True, custom_msg=""):
        if is_loading:
            self.statusBanner.setStyleSheet("background-color: #45475a; border-radius: 6px;")
            self.lblStatusMsg.setStyleSheet("font-size: 13px; font-weight: bold; color: #f9e2af;")
            self.dots_count = 0
            self._loading_message = custom_msg or "Đang xử lý dữ liệu..."
            self.lblStatusMsg.setText(self._loading_message)
            self.anim_timer.start(400)

            if hasattr(self, 'movie'):
                self.movie.start()

            if not getattr(self, "_owns_wait_cursor", False):
                QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
                self._owns_wait_cursor = True
        else:
            self.anim_timer.stop()
            if hasattr(self, 'movie'):
                self.movie.stop()

            if getattr(self, "_owns_wait_cursor", False):
                QApplication.restoreOverrideCursor()
                self._owns_wait_cursor = False

            if success:
                self.statusBanner.setStyleSheet("background-color: #2e3c38; border-radius: 6px;")
                self.lblStatusMsg.setStyleSheet("font-size: 13px; font-weight: bold; color: #a6e3a1;")
                self.lblStatusMsg.setText(custom_msg if custom_msg else "✅ Đã tải dữ liệu thành công!")
            else:
                self.statusBanner.setStyleSheet("background-color: #442a38; border-radius: 6px;")
                self.lblStatusMsg.setStyleSheet("font-size: 13px; font-weight: bold; color: #f38ba8;")
                self.lblStatusMsg.setText(custom_msg if custom_msg else "❌ Lỗi đọc dữ liệu!")

    def _update_loading_animation(self):
        self.dots_count = (self.dots_count % 4) + 1
        dots = " ." * self.dots_count
        icons = ["⏳", "⌛"]
        current_icon = icons[self.dots_count % 2]
        message = getattr(self, "_loading_message", "Đang xử lý dữ liệu")
        self.lblStatusMsg.setText(f"{message}{dots}")

    def copy_table_to_clipboard(self, selection_only=False):
        df = self.table_model._data
        if df.empty:
            return

        selected_indexes = self.table.selectedIndexes()

        if selection_only and selected_indexes:
            rows = sorted(list(set(index.row() for index in selected_indexes)))
            cols = sorted(list(set(index.column() for index in selected_indexes)))
            sub_df = df.iloc[rows, cols]
            sub_df.to_clipboard(sep="\t", index=False, header=False)
        else:
            df.to_clipboard(sep="\t", index=False)

        QMessageBox.information(self, "Thông báo", "Đã chép dữ liệu.")

    def refresh(self):
        self.df = pd.DataFrame()
        self.filtered = pd.DataFrame()
        self.wave_df = pd.DataFrame()
        self.current_scope_df = pd.DataFrame()
        self.current_status = ""
        self.start_time = None

        self.statusList.clear()
        self.waveList.clear()
        self.perfList.clear()
        self.searchBox.clear()

        self.lblTotal.setText("0")
        self.lblOutbound.setText("0")
        self.lblPercent.setText("0.00%")
        self.lblTimer.setText("0.00s")

        self.table_model.update_data(pd.DataFrame())

        self.chartWaveCanvas.plot_pie(pd.Series(), "Wave Type")
        self.chartCategoryCanvas.plot_pie(pd.Series(), "Category")

        self.lblRowCount.setText("📊 Tổng dòng: 0 | Đã chọn: 0")
        self.lblSelectedDetail.setText("💡 Chi tiết đơn: Click vào dòng để xem")

        self.statusBanner.setStyleSheet("background-color: #313244; border-radius: 6px;")
        self.lblStatusMsg.setStyleSheet("font-size: 13px; font-weight: bold; color: #cdd6f4;")
        self.lblStatusMsg.setText("🔄 Đã làm mới bảng làm việc.")

    def start_folder_watcher(self, path=None):
        if hasattr(self, 'watcher_thread') and self.watcher_thread.isRunning():
            self.watcher_thread.stop()

        if not path:
            path = os.path.join(os.path.expanduser("~"), "Downloads")

        self.current_watch_path = path
        if not os.path.isdir(path):
            return
        self.watcher_thread = WatcherThread(self.current_watch_path)
        self.watcher_thread.file_detected.connect(self._on_auto_file_detected)
        self.watcher_thread.start()

    def select_watch_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục theo dõi", self.current_watch_path)
        if folder:
            self.start_folder_watcher(folder)

    def _on_auto_file_detected(self, filepath):
        if self.chkAutoWatch.isChecked():
            self.read_excel_file(filepath)

    def _start_loader(self, mode, source=None):
        request = (mode, source)
        if self.loader_thread is not None and self.loader_thread.isRunning():
            # Không ghi đè reference QThread đang chạy. Giữ yêu cầu mới nhất để
            # tự chạy ngay sau tác vụ hiện tại (hữu ích khi watcher bắt file liên tiếp).
            if request != self._active_load:
                self._pending_load = request
            self.set_banner_status(
                is_loading=True,
                custom_msg="⌛ Đang đọc dữ liệu; yêu cầu mới sẽ được xử lý ngay sau đó..."
            )
            return False

        self.set_banner_status(is_loading=True)
        self.start_time = time.time()
        self._loader_started_at = self.start_time
        self._active_load = request

        thread = DataLoaderThread(mode=mode, source=source)
        self.loader_thread = thread
        thread.data_loaded.connect(self._on_data_loaded)
        thread.error.connect(self._on_data_error)
        thread.finished.connect(self._on_loader_thread_finished)
        thread.start()
        return True

    def read_excel_file(self, filepath):
        self._start_loader(mode='excel', source=filepath)

    def load_excel(self):
        file, _ = QFileDialog.getOpenFileName(self, "Open Excel", "", "Excel (*.xlsx *.xls)")
        if file:
            self.read_excel_file(file)

    def load_clipboard(self):
        self._start_loader(mode='clipboard')

    def _on_data_loaded(self, df):
        self.df = df
        self.process()

        if self._loader_started_at:
            elapsed = time.time() - self._loader_started_at
            self.lblTimer.setText(f"{elapsed:.2f}s")

        self.set_banner_status(is_loading=False, success=True)

    def _on_data_error(self, err_msg):
        self.set_banner_status(is_loading=False, success=False, custom_msg=f"❌ Lỗi đọc dữ liệu: {err_msg}")
        QMessageBox.warning(self, "Lỗi đọc dữ liệu", err_msg)

    def _on_loader_thread_finished(self):
        self.loader_thread = None
        self._loader_started_at = None
        self._active_load = None

        pending = self._pending_load
        self._pending_load = None
        if pending is not None:
            mode, source = pending
            QTimer.singleShot(0, lambda m=mode, s=source: self._start_loader(m, s))

    def process(self):
        if self.df.empty:
            return

        if "New 3PL" in self.df.columns:
            tpl_options = sorted([str(x).strip() for x in self.df["New 3PL"].dropna().unique()])
            default_3pl = self.config.get("default_3pl", ["SPX Express", "SPX Express NDD - Trong Ngày"])
            self.combo3PL.populate_items(tpl_options, default_3pl)

        if "Buyer State" in self.df.columns:
            state_options = sorted([str(x).strip() for x in self.df["Buyer State"].dropna().unique()])
            default_state = self.config.get("default_buyer_state", ["Hà Nội", "Thành phố Hà Nội"])
            self.comboState.populate_items(state_options, default_state)

        self.apply_filter()

    def _on_filter_changed(self):
        self.combo3PL.update_text()
        self.comboState.update_text()
        self.apply_filter()

    def apply_filter(self):
        if self.df.empty:
            return

        df = self.df.copy()

        selected_3pl = self.combo3PL.get_checked_items()
        if selected_3pl and "New 3PL" in df.columns:
            df = df[df["New 3PL"].astype(str).str.strip().isin(selected_3pl)]

        selected_state = self.comboState.get_checked_items()
        if selected_state and "Buyer State" in df.columns:
            df = df[df["Buyer State"].astype(str).str.strip().isin(selected_state)]

        if "WMS Order No" in df.columns:
            # Chỉ xóa trùng khi WMS Order No thực sự có giá trị.
            # Các dòng trống/NaN không được coi là cùng một đơn.
            order_key = df["WMS Order No"].astype("string").str.strip()
            has_order_no = order_key.notna() & order_key.ne("")
            keep_mask = ~has_order_no | ~order_key.duplicated(keep="first")
            df = df[keep_mask].copy()

        self.filtered = df
        self.current_scope_df = df.copy()

        outbound = 0
        total_valid = len(df)

        if "Status" in df.columns:
            status_series = df["Status"].astype("string").fillna("").str.strip().str.casefold()

            is_cancel = status_series.isin(["cancelled", "canceled", "cancel"])
            cancel_count = int(is_cancel.sum())

            total_valid = len(df) - cancel_count
            outbound = int((status_series == "outbound").sum())

        percent = (outbound / total_valid * 100) if total_valid > 0 else 0

        self.lblTotal.setText(f"{total_valid:,}")
        self.lblOutbound.setText(f"{outbound:,}")
        self.lblPercent.setText(f"{percent:.2f}%")

        self.load_status()
        self.update_charts(df)
        self.update_performance_tab(df)

    def update_charts(self, df):
        if df.empty:
            self.chartWaveCanvas.plot_pie(pd.Series(), "Wave Type")
            self.chartCategoryCanvas.plot_pie(pd.Series(), "Category")
            return

        if "Wave Type" in df.columns:
            wave_counts = df["Wave Type"].dropna().value_counts()
            self.chartWaveCanvas.plot_pie(wave_counts, "Tỷ lệ Wave Type")
        else:
            self.chartWaveCanvas.plot_pie(pd.Series(), "Wave Type")

        if "Category" in df.columns:
            cat_counts = df["Category"].dropna().value_counts()
            self.chartCategoryCanvas.plot_pie(cat_counts, "Tỷ lệ Category")
        else:
            self.chartCategoryCanvas.plot_pie(pd.Series(), "Category")

    def save_defaults(self):
        self.config["default_3pl"] = self.combo3PL.get_checked_items()
        self.config["default_buyer_state"] = self.comboState.get_checked_items()
        
        if save_config(self.config):
            QMessageBox.information(
                self, "Thành công",
                f"Đã lưu mặc định thành công!\n- 3PL: {self.config['default_3pl']}\n- Tỉnh/Thành: {self.config['default_buyer_state']}"
            )
        else:
            QMessageBox.warning(self, "Lỗi", "Không thể lưu mặc định!")

    def load_status(self):
        self.statusList.clear()
        self.waveList.clear()

        if self.filtered.empty or "Status" not in self.filtered.columns:
            self.show_table(self.filtered)
            return

        cancel_keywords = ["cancelled", "canceled", "cancel"]
        status_display = self.filtered["Status"].astype("string").fillna("").str.strip()
        status_key = status_display.str.casefold()
        valid_mask = ~status_key.isin(cancel_keywords) & status_display.ne("")

        total_valid = int(valid_mask.sum())
        key_counts = status_key[valid_mask].value_counts()

        for key, qty in key_counts.items():
            first_idx = status_key[valid_mask & status_key.eq(key)].index[0]
            status = status_display.loc[first_idx]
            p = (qty / total_valid * 100) if total_valid > 0 else 0
            self.statusList.addItem(f"{status}    {qty} ({p:.2f}%)")

        self.show_table(self.filtered)

    def search_order(self):
        keyword = self.searchBox.text().strip()
        df = self.current_scope_df.copy()
        
        if df.empty:
            return

        if keyword == "":
            self.show_table(df)
            return

        existing_allowed_cols = [col for col in ALLOWED_COLUMNS if col in df.columns]
        target_df = df[existing_allowed_cols]

        mask = pd.Series(False, index=target_df.index)
        for col in target_df.columns:
            mask |= target_df[col].astype(str).str.contains(keyword, case=False, na=False)

        filtered_df = df[mask]
        self.show_table(filtered_df, search_keyword=keyword)

    def filter_basket_orders(self):
        # Mã rổ là một bộ lọc độc lập: luôn bắt đầu từ dữ liệu sau bộ lọc
        # New 3PL / Buyer State, không phụ thuộc Status/Wave đã click trước đó.
        df = self.filtered.copy() if not self.filtered.empty else self.df.copy()

        if df.empty:
            self.current_scope_df = pd.DataFrame()
            self.show_table(pd.DataFrame())
            QMessageBox.information(self, "Thông báo", "Chưa có dữ liệu để lọc.")
            return

        if "Status" not in df.columns:
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy cột 'Status' trong dữ liệu!")
            return

        status_clean = df["Status"].astype("string").fillna("").str.strip().str.casefold()
        df_picked = df[status_clean == "picked"].copy()

        if df_picked.empty:
            self.current_scope_df = pd.DataFrame()
            self.wave_df = pd.DataFrame()
            self.show_table(pd.DataFrame())
            self.update_charts(pd.DataFrame())
            QMessageBox.information(self, "Thông báo", "Không có đơn hàng nào ở trạng thái 'Picked'.")
            return

        col_device = None
        for col in df_picked.columns:
            cleaned_col = str(col).strip().lower()
            if cleaned_col in ["device id", "device_id", "deviceid"]:
                col_device = col
                break

        if not col_device:
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy cột 'Device ID' trong tệp dữ liệu!")
            return

        df_picked[col_device] = df_picked[col_device].astype(str).str.strip()
        mask = df_picked[col_device].str.contains('BSK', case=False, na=False, regex=False)
        basket_df = df_picked[mask].copy()

        if basket_df.empty:
            self.current_scope_df = pd.DataFrame()
            self.wave_df = pd.DataFrame()
            self.show_table(pd.DataFrame())
            self.update_charts(pd.DataFrame())
            QMessageBox.information(self, "Thông báo", f"Không tìm thấy mã rổ (BSK...) nào trong cột '{col_device}' ở trạng thái Picked.")
            return

        basket_df = basket_df.drop_duplicates(subset=[col_device], keep='first')

        self.current_scope_df = basket_df
        self.show_table(basket_df)
        self.update_charts(basket_df)

        QMessageBox.information(
            self, "Kết quả",
            f"Đã tìm thấy {len(basket_df)} mã rổ duy nhất (Device ID) ở trạng thái Picked."
        )

    def click_status(self):
        if self.statusList.currentItem() is None:
            return

        text = self.statusList.currentItem().text()
        m = re.match(r"^(.*?)\s+\d+\s+\(", text)
        status = m.group(1).strip() if m else text.split("(")[0].strip()

        self.current_status = status
        status_series = self.filtered["Status"].astype("string").fillna("").str.strip().str.casefold()
        df = self.filtered[status_series == status.casefold()].copy()
        
        self.wave_df = df
        self.current_scope_df = df.copy()
        
        self.waveList.clear()

        if "Wave Type" not in df.columns:
            self.show_table(df)
            return

        total = len(df)
        wave_display = df["Wave Type"].astype("string").fillna("").str.strip()
        wave_key = wave_display.str.casefold()
        valid_wave = wave_display.ne("")
        count = wave_key[valid_wave].value_counts()

        for key, qty in count.items():
            first_idx = wave_key[valid_wave & wave_key.eq(key)].index[0]
            wave = wave_display.loc[first_idx]
            p = qty / total * 100 if total > 0 else 0
            self.waveList.addItem(f"{wave}    {qty} ({p:.2f}%)")

        self.show_table(df)
        self.update_charts(df)

    def click_wave(self):
        if self.waveList.currentItem() is None:
            return

        text = self.waveList.currentItem().text()
        m = re.match(r"^(.*?)\s+\d+\s+\(", text)
        wave = m.group(1).strip() if m else text.split("(")[0].strip()

        wave_series = self.wave_df["Wave Type"].astype("string").fillna("").str.strip().str.casefold()
        df = self.wave_df[wave_series == wave.casefold()].copy()
        self.current_scope_df = df.copy()
        
        self.show_table(df)
        self.update_charts(df)

    def show_table(self, df, search_keyword=""):
        if df.empty:
            self.table_model.update_data(pd.DataFrame())
            self.update_bottom_status_bar()
            return

        existing_allowed_cols = [col for col in ALLOWED_COLUMNS if col in df.columns]
        display_df = df[existing_allowed_cols]

        self.table_model.update_data(display_df, search_keyword=search_keyword)
        self.update_bottom_status_bar()

    def export_excel(self):
        if self.current_scope_df.empty:
            QMessageBox.warning(self, "Lỗi", "Không có dữ liệu để xuất Excel!")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Xuất File Excel", "WMS_Export.xlsx", "Excel Files (*.xlsx)")
        if file_path:
            try:
                existing_allowed_cols = [col for col in ALLOWED_COLUMNS if col in self.current_scope_df.columns]
                export_df = self.current_scope_df[existing_allowed_cols]
                export_df.to_excel(file_path, index=False)
                QMessageBox.information(self, "Thành công", f"Đã xuất dữ liệu thành công ra file:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể xuất file: {str(e)}")


    def closeEvent(self, event):
        self._pending_load = None
        if (self.cotTab.parser and self.cotTab.parser.isRunning()) or not self.cotTab.bridge.stop():
            self.set_banner_status(True, custom_msg="Đang dừng tác vụ Chrome, hãy đóng app lại sau ít giây...")
            event.ignore()
            return

        if self.loader_thread is not None and self.loader_thread.isRunning():
            if not self.loader_thread.wait(3000):
                self.set_banner_status(
                    is_loading=True,
                    custom_msg="⌛ Đang hoàn tất đọc dữ liệu trước khi đóng ứng dụng..."
                )
                event.ignore()
                return

        if hasattr(self, "watcher_thread") and self.watcher_thread is not None:
            if self.watcher_thread.isRunning():
                self.watcher_thread.stop()

        event.accept()



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WMSDashboard()
    window.show()
    sys.exit(app.exec())


