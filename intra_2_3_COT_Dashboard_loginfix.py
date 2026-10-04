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

# --- TÍCH HỢP PLAYWRIGHT ĐỂ ĐĂNG NHẬP WMS LẤY COOKIE ---
from playwright.sync_api import sync_playwright

# --- TÍCH HỢP MATPLOTLIB VÀO PYSIDE6 ---
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# ================= CẤU HÌNH PHIÊN BẢN & AUTO-UPDATE =================
CURRENT_VERSION = "2.3.4_COT_status_200"
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

# ================= THREAD GỌI API WMS THEO KHUNG COT =================
# ================= WMS API / COT DASHBOARD =================
WMS_SEARCH_ORDER_URL = "https://wms.ssc.shopee.vn/api/v2/apps/process/outbound/salesorder/search_order"
VN_TZ = timezone(timedelta(hours=7))
WMS_PAGE_SIZE = 200
WMS_PAGE_INTERVAL_SECONDS = 1.0

COT_STATUS_GROUPS = {
    "pick": "0,9,2",
    "check": "3,15,16,12,13",
    "pack": "6,5",
    "wis": "10,11,7",
    "pending": "0,9,2,3,15,16,12,13,6,5,10,11,7",
    "total": "0,9,2,3,15,16,12,13,6,5,10,11,7,8",
}

COT_METRIC_LABELS = {
    "pick": "Chưa Pick",
    "check": "Chưa Check",
    "pack": "Chưa Pack",
    "wis": "Chưa WIS",
    "pending": "Chưa Outbound",
    "total": "Tổng đơn",
}

# Các mã đang dùng trong bộ lọc WMS cũ; ưu tiên tên do API trả về.
COT_STATUS_NAMES = dict(zip(
    COT_STATUS_GROUPS["total"].split(","),
    ["Created", "Pending Pick", "Picking", "Picked", "Checking", "Checked",
     "Pre Sorting", "Pre Sorted", "Sorting", "Sorted", "Packing", "Packed", "Shipping", "Outbound"],
))
COT_STATUS_ORDER = ["Created", "Pending Pick", "Picking", "Picked", "Pick Fail", "Checking",
                    "Checked", "Pre Sorting", "Pre Sorted", "Sorting", "Sorted", "Packing",
                    "Packed", "Shipping", "Outbound", "Cancel"]


def _order_status_name(row):
    for key in ("order_status_name", "status_name", "order_status_text", "status_text", "status", "order_status"):
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        name = value.strip()
        if name.casefold() in ("cancelled", "canceled", "cancel"):
            return "Cancel"
        for known in COT_STATUS_ORDER:
            if name.casefold().replace("_", " ") == known.casefold():
                return known
    value = row.get("order_status", row.get("status", ""))
    try:
        code = str(int(value))
    except (ValueError, TypeError):
        return str(value).strip() or "Chưa có trạng thái"
    # Không đoán mã Cancel/Pick Fail chưa có trong tài liệu nguồn.
    return COT_STATUS_NAMES.get(code, f"Mã trạng thái {code}")


def _dedupe_cot_orders(rows):
    result, seen = [], set()
    for row in rows:
        key = str(row.get("order_number") or "").strip()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        result.append(row)
    return result


class WMSAuthError(RuntimeError):
    pass


def _wms_post(cookie_str, payload, timeout=15):
    if not cookie_str:
        raise WMSAuthError("Chưa có Cookie WMS. Vui lòng đăng nhập WMS trước.")

    data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        WMS_SEARCH_ORDER_URL,
        data=data_bytes,
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "X-CCTV-Tenant-Id": "WMS",
            "Cookie": cookie_str,
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://wms.ssc.shopee.vn",
            "Referer": "https://wms.ssc.shopee.vn/",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        if e.code in (401, 403):
            raise WMSAuthError(f"WMS từ chối phiên đăng nhập (HTTP {e.code}). Vui lòng đăng nhập lại.")
        if e.code == 429:
            raise RuntimeError("HTTP 429: WMS đang giới hạn yêu cầu. Đã dừng tải, không tự thử lại.")
        raise RuntimeError(f"HTTP {e.code}: {body[:300] or e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Không kết nối được WMS: {e.reason}")

    try:
        res = json.loads(raw)
    except Exception:
        lower = raw.lower()
        if "<html" in lower or "<!doctype" in lower or "login" in lower:
            raise WMSAuthError("WMS trả về trang đăng nhập thay vì JSON. Cookie có thể đã hết hạn.")
        raise RuntimeError("Phản hồi WMS không phải JSON hợp lệ.")

    if not isinstance(res, dict):
        raise RuntimeError("Phản hồi WMS có định dạng không hợp lệ.")

    if res.get("retcode") == 10001:
        raise WMSAuthError("Phiên WMS đã hết hạn. Vui lòng đăng nhập lại.")

    if res.get("retcode") != 0:
        raise RuntimeError(str(res.get("message") or f"WMS retcode={res.get('retcode')}"))

    data = res.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("WMS không trả về trường data hợp lệ.")
    return data


def _wms_post_retry(cookie_str, payload, retries=0, timeout=15):
    # Giữ tên hàm cũ; mọi lỗi đều dừng, chỉ người dùng mới bấm tải lại.
    return _wms_post(cookie_str, payload, timeout=timeout)


def _build_wms_payload(cot_def, status_list, pageno=1, count=WMS_PAGE_SIZE, is_get_total=1, channel_override=None):
    payload = {
        "order_status_list": status_list,
        "pageno": int(pageno),
        "count": int(count),
        "is_get_total": int(bool(is_get_total)),
    }

    beg_ts = int(cot_def["beg"].timestamp())
    end_ts = int(cot_def["end"].timestamp())

    if cot_def.get("cutoff"):
        payload["beg_cut_off_time"] = beg_ts
        payload["end_cut_off_time"] = end_ts
    else:
        payload["beg_ctime"] = beg_ts
        payload["end_ctime"] = end_ts

    channels = channel_override if channel_override is not None else cot_def.get("channels")
    if channels:
        payload["channel_id_list"] = list(channels)

    return payload


def _extract_total(data):
    if "total" in data and data.get("total") is not None:
        try:
            return int(data.get("total"))
        except (TypeError, ValueError):
            pass
    lst = data.get("list")
    return len(lst) if isinstance(lst, list) else 0


def _purchase_timestamp(row):
    value = row.get("purchase_time")
    try:
        timestamp = float(value)
        if timestamp > 10**12:
            timestamp /= 1000
        if timestamp > 0 and math.isfinite(timestamp):
            return timestamp
    except (TypeError, ValueError):
        pass
    raise RuntimeError("WMS thiếu Purchase Time; không thể xác định đúng khung Intra City.")


def _filter_purchase_window(rows, beg, end):
    # Khoảng nửa mở để đơn đúng 23:00 / 02:00 / 16:00 / 20:00 chỉ thuộc một COT.
    begin, finish = beg.timestamp(), end.timestamp()
    return [row for row in rows if begin <= _purchase_timestamp(row) < finish]


def _filter_created_window(rows, beg, end):
    begin, finish = beg.timestamp(), end.timestamp()
    result = []
    for row in rows:
        try:
            stamp = float(row["ctime"])
            if stamp > 10**12:
                stamp /= 1000
        except (KeyError, TypeError, ValueError):
            raise RuntimeError("WMS thiếu Create Time; không thể xác định đúng khung cắt Pick.")
        if begin <= stamp < finish:
            result.append(row)
    return result


class COTOrderListThread(QThread):
    list_ready = Signal(str, object, int)
    progress = Signal(str, int, int)
    auth_error = Signal(str, str)
    error = Signal(str, str)

    def __init__(self, request_id, cookie_str, cot_def, metric_key, page_size=WMS_PAGE_SIZE):
        super().__init__()
        self.request_id = request_id
        self.cookie_str = cookie_str
        self.cot_def = cot_def
        self.metric_key = metric_key
        self.page_size = page_size
        self._last_api_started = None

    def _fetch_page(self, payload):
        # Các trang/đợt của cùng một lần bấm chạy tuần tự, tối đa 1 lần/giây.
        if self._last_api_started is not None:
            while time.monotonic() - self._last_api_started < WMS_PAGE_INTERVAL_SECONDS:
                if self.isInterruptionRequested():
                    return None
                time.sleep(0.05)
        if self.isInterruptionRequested():
            return None
        self._last_api_started = time.monotonic()
        try:
            return _wms_post_retry(self.cookie_str, payload)
        except WMSAuthError:
            raise
        except Exception as exc:
            raise RuntimeError(f"{exc} (trang {payload['pageno']}, yêu cầu {payload['count']} đơn/trang)") from exc

    def _fetch_for_channels(self, channels, cot_query=None):
        cot_query = cot_query or self.cot_def
        # Không loại Cancel/Pick Fail trước khi tính thống kê trạng thái.
        status_list = "" if self.metric_key == "total" else COT_STATUS_GROUPS[self.metric_key]
        first_payload = _build_wms_payload(
            cot_query, status_list, pageno=1, count=self.page_size,
            is_get_total=1, channel_override=channels
        )
        first = self._fetch_page(first_payload)
        if first is None:
            return [], 0
        total = _extract_total(first)
        rows = list(first.get("list") or [])
        loaded = len(rows)
        self.progress.emit(self.request_id, loaded, total)

        if total <= loaded:
            return rows, total
        if loaded < self.page_size:
            raise RuntimeError(
                f"WMS trả {loaded}/{self.page_size} đơn ở trang 1 dù báo tổng {total:,} đơn. "
                "Đã dừng để tránh bỏ sót đơn; cần kiểm tra giới hạn phân trang của API."
            )

        total_pages = (total + self.page_size - 1) // self.page_size
        for page in range(2, total_pages + 1):
            if self.isInterruptionRequested():
                break

            payload = _build_wms_payload(
                cot_query, status_list, pageno=page, count=self.page_size,
                is_get_total=0, channel_override=channels
            )
            data = self._fetch_page(payload)
            if data is None:
                break
            part = data.get("list") or []
            if not isinstance(part, list):
                part = []
            rows.extend(part)
            loaded = len(rows)
            self.progress.emit(self.request_id, min(loaded, total), total)

            if not part:
                break

        return rows, total

    def run(self):
        try:
            all_rows = []
            total_expected = 0

            if self.cot_def.get("cutoff_ranges"):
                # Một khung Purchase Time có thể có hai đợt bàn giao / Cut-Off.
                for beg, end in self.cot_def["cutoff_ranges"]:
                    if self.isInterruptionRequested():
                        break
                    query = dict(self.cot_def, beg=beg, end=end)
                    rows, total = self._fetch_for_channels(self.cot_def.get("channels"), query)
                    all_rows.extend(rows)
                    total_expected += total
            elif self.cot_def.get("composite_channels"):
                for child_channels in self.cot_def["composite_channels"]:
                    if self.isInterruptionRequested():
                        break
                    rows, total = self._fetch_for_channels(child_channels)
                    source_ch = ",".join(child_channels)
                    for row in rows:
                        if isinstance(row, dict):
                            copied = dict(row)
                            copied["_source_channel"] = source_ch
                            all_rows.append(copied)
                        else:
                            all_rows.append(row)
                    total_expected += total
            else:
                all_rows, total_expected = self._fetch_for_channels(self.cot_def.get("channels"))

            if not self.isInterruptionRequested():
                if len(all_rows) < total_expected:
                    raise RuntimeError(f"API trả thiếu trang: {len(all_rows):,}/{total_expected:,} đơn. Hãy tải lại COT này.")
                if self.cot_def.get("purchase_beg"):
                    all_rows = _filter_purchase_window(
                        all_rows, self.cot_def["purchase_beg"], self.cot_def["purchase_end"]
                    )
                    total_expected = len(all_rows)
                elif not self.cot_def.get("cutoff"):
                    all_rows = _filter_created_window(all_rows, self.cot_def["beg"], self.cot_def["end"])
                    total_expected = len(all_rows)
                self.list_ready.emit(self.request_id, all_rows, total_expected)
        except WMSAuthError as e:
            self.auth_error.emit(self.request_id, str(e))
        except Exception as e:
            self.error.emit(self.request_id, str(e))


# ================= THREAD TỰ ĐỘNG ĐĂNG NHẬP & LẤY COOKIE =================
class WMSLoginThread(QThread):
    login_success = Signal(str)
    login_failed = Signal(str)
    progress = Signal(str)
    LOGIN_TIMEOUT = 180
    WAREHOUSE_SWITCH_DELAY = 5

    @staticmethod
    def _is_logged_in_page(page):
        """Nhận diện giao diện WMS; không gọi API và không đoán tên cookie."""
        parsed = urllib.parse.urlsplit(page.url)
        if parsed.scheme != "https" or parsed.hostname != "wms.ssc.shopee.vn":
            return False
        path = urllib.parse.unquote(parsed.path).lower().rstrip("/")
        if any(part in path.split("/") for part in ("login", "signin", "sso", "auth")):
            return False
        if page.locator("input[type='password']:visible").count():
            return False
        # Menu xuất hiện trong video. Chỉ URL /home thôi chưa đủ vì SPA
        # có thể chưa kiểm tra phiên và đang chuyển trở lại trang login.
        visible_menus = sum(
            page.get_by_text(label, exact=True).first.is_visible()
            for label in ("Sales Outbound", "Inbound", "MT Inbound", "Return Inbound")
        )
        known_route = path == "/home" or path == "/v2" or path.startswith("/v2/")
        return visible_menus >= (1 if known_route else 2)

    @staticmethod
    def _cookie_header(cookies):
        # context.cookies(API_URL) đã lọc domain, secure và path. Không lấy
        # cookie của trang SSO khác. Giữ thứ tự path cụ thể trước path chung.
        cookies = sorted(cookies, key=lambda c: len(c.get("path", "/")), reverse=True)
        return "; ".join(
            f"{cookie['name']}={cookie['value']}"
            for cookie in cookies
            if cookie.get("name") and cookie.get("value") is not None
        )

    def run(self):
        cookie_str = ""
        failure = ""
        deadline = time.monotonic() + self.LOGIN_TIMEOUT
        try:
            with sync_playwright() as p:
                browser = None
                try:
                    launch_errors = []
                    # Chrome có sẵn là lựa chọn đầu; Chromium đi kèm EXE là dự phòng.
                    for channel in ("chrome", None):
                        if self.isInterruptionRequested():
                            return
                        try:
                            options = {"headless": False, "timeout": 15000}
                            if channel:
                                options["channel"] = channel
                            browser = p.chromium.launch(**options)
                            break
                        except Exception:
                            launch_errors.append(channel or "Chromium")
                    if browser is None:
                        raise RuntimeError(
                            "Không mở được Chrome hoặc Chromium đi kèm. "
                            "Nếu chạy từ mã nguồn, cài Chrome hoặc chạy: python -m playwright install chromium"
                        )

                    context = browser.new_context()
                    context.set_default_timeout(1500)
                    page = context.new_page()
                    self.progress.emit("⌛ Hãy đăng nhập WMS trong cửa sổ trình duyệt vừa mở...")
                    try:
                        page.goto("https://wms.ssc.shopee.vn", wait_until="domcontentloaded", timeout=15000)
                    except Exception:
                        if page.is_closed() or not browser.is_connected():
                            raise RuntimeError("Bạn đã đóng cửa sổ đăng nhập WMS.")
                        # Trang chậm vẫn có thể tiếp tục tải; vòng lặp có deadline riêng.

                    stable_page = None
                    stable_since = None
                    while time.monotonic() < deadline:
                        if self.isInterruptionRequested():
                            return
                        if not browser.is_connected():
                            failure = "Bạn đã đóng cửa sổ đăng nhập WMS trước khi app nhận được phiên."
                            break
                        pages = [candidate for candidate in context.pages if not candidate.is_closed()]
                        if not pages:
                            failure = "Bạn đã đóng toàn bộ tab đăng nhập WMS."
                            break
                        recognized = None
                        for candidate in reversed(pages):
                            try:
                                if self._is_logged_in_page(candidate):
                                    recognized = candidate
                                    break
                            except Exception:
                                # Điều hướng hoặc đóng tab trong lúc kiểm tra: thử lại ở lượt sau.
                                continue

                        if recognized is None:
                            stable_page = stable_since = None
                        elif recognized is not stable_page:
                            stable_page, stable_since = recognized, time.monotonic()
                        elif time.monotonic() - stable_since >= 1.2:
                            remaining = 1.2 + self.WAREHOUSE_SWITCH_DELAY - (time.monotonic() - stable_since)
                            if remaining > 0:
                                self.progress.emit(
                                    f"⌛ Đã vào WMS — hãy đổi kho. Lấy phiên và đóng Chrome sau {math.ceil(remaining)} giây..."
                                )
                            else:
                                # Lấy cookie sau thời gian đổi kho để giữ phiên mới nhất.
                                self.progress.emit("⌛ Đang lấy phiên sau khi đổi kho...")
                                cookies = context.cookies([
                                    "https://wms.ssc.shopee.vn/api/v2/apps/process/outbound/salesorder/search_order"
                                ])
                                cookie_str = self._cookie_header(cookies)
                                if cookie_str:
                                    break
                                self.progress.emit("⌛ Đã vào WMS, đang chờ cookie của phiên...")
                        # Cho Playwright xử lý điều hướng/tab SSO thay vì sleep chặn sự kiện.
                        try:
                            pages[-1].wait_for_timeout(300)
                        except Exception:
                            continue
                    if not cookie_str and not failure:
                        failure = (
                            "Hết thời gian chờ đăng nhập WMS (180 giây). "
                            "Hãy đăng nhập lại và chờ trang /home hiện menu WMS."
                        )
                finally:
                    if browser is not None:
                        try:
                            browser.close()
                        except Exception:
                            pass
        except Exception as exc:
            failure = f"Không hoàn tất đăng nhập WMS: {exc}"

        if self.isInterruptionRequested():
            return
        # Chỉ báo về GUI sau khi đã đóng trình duyệt và giải phóng Playwright.
        if cookie_str:
            self.login_success.emit(cookie_str)
        else:
            self.login_failed.emit(failure or "Chưa lấy được phiên WMS.")


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

        # ===== WMS / COT Dashboard =====
        self.login_thread = None
        self.cot_list_thread = None
        self.cot_definitions = []
        self.cot_definition_map = {}
        self.cot_cache = {}
        self.cot_current_df = pd.DataFrame()
        self.cot_current_total = 0
        self.cot_current_selection = None
        self._active_cot_request_id = None
        self._active_cot_cache_key = None
        self._pending_cot_list_request = None
        self.cot_current_rows = []
        self.cot_active_slot = None
        self.cot_buttons = {}
        self.cot_metric_buttons = {}
        self._cot_request_serial = 0
        self._cot_data_ready = False

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
            "🟢 Đã có phiên WMS đã lưu" if self.config.get("wms_cookie") else "⚪ Chưa đăng nhập WMS"
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
        self.cotTab = QWidget()
        cot_root = QVBoxLayout(self.cotTab)
        cot_root.setContentsMargins(8, 8, 8, 8)
        cot_root.setSpacing(8)

        cot_toolbar = QHBoxLayout()
        self.cotService = QComboBox()
        self.cotService.addItems(["Intra City", "SDD", "AhaMove", "SPX Cồng kềnh", "GHN"])
        self.cotService.setMinimumWidth(150)
        self.cotDate = QDateEdit(QDate.currentDate())
        self.cotDate.setDate(QDate(datetime.now(VN_TZ).year, datetime.now(VN_TZ).month, datetime.now(VN_TZ).day))
        self.cotDate.setDisplayFormat("dd/MM/yyyy")
        self.cotDate.setCalendarPopup(True)
        self.cotDate.setToolTip("Ngày kết thúc khung COT. Intra COT 1/2 và các khung qua đêm bắt đầu từ ngày trước.")
        self.btnCotReloadList = QPushButton("🔄 Tải lại COT")
        self.btnCotCopyList = QPushButton("📄 Copy")
        self.btnCotExportList = QPushButton("📤 Export")
        self.searchCotBox = QLineEdit()
        self.searchCotBox.setPlaceholderText("🔍 Tìm trong COT đang chọn...")
        cot_toolbar.addWidget(QLabel("Nhóm:"))
        cot_toolbar.addWidget(self.cotService)
        cot_toolbar.addWidget(QLabel("Ngày:"))
        cot_toolbar.addWidget(self.cotDate)
        cot_toolbar.addWidget(self.btnCotReloadList)
        cot_toolbar.addWidget(self.btnCotCopyList)
        cot_toolbar.addWidget(self.btnCotExportList)
        cot_toolbar.addWidget(self.searchCotBox, 1)
        cot_root.addLayout(cot_toolbar)

        self.cotButtonRow = QHBoxLayout()
        cot_root.addLayout(self.cotButtonRow)
        self.cotSlotPanel = QWidget()
        self.cotSlotRow = QHBoxLayout(self.cotSlotPanel)
        self.cotSlotRow.setContentsMargins(0, 0, 0, 0)
        cot_root.addWidget(self.cotSlotPanel)
        self.cotSlotPanel.hide()

        self.lblCotSelection = QLabel("Chọn một nút COT để tải đơn của COT đó.")
        self.lblCotSelection.setStyleSheet("color: #89b4fa; font-weight: bold;")
        cot_root.addWidget(self.lblCotSelection)
        self.lblCotHandoff = QLabel("Intra City: theo Purchase Time. SDD / AhaMove / SPX: theo giờ cắt Pick.")
        self.lblCotHandoff.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.lblCotHandoff.setWordWrap(True)
        cot_root.addWidget(self.lblCotHandoff)

        metric_row = QHBoxLayout()
        self.cotMetricGroup = QButtonGroup(self)
        for key, label in COT_METRIC_LABELS.items():
            button = QPushButton(f"{label}: —")
            button.setCheckable(True)
            button.setEnabled(False)
            button.setProperty("cotMetric", True)
            button.clicked.connect(lambda checked=False, mk=key: self._select_cot_metric(mk))
            self.cotMetricGroup.addButton(button)
            self.cot_metric_buttons[key] = button
            metric_row.addWidget(button, 1)
        self.cot_metric_buttons["total"].setChecked(True)
        cot_root.addLayout(metric_row)

        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Trạng thái:"))
        self.cotStatusFilter = QComboBox()
        self.cotStatusFilter.setMinimumWidth(250)
        self.cotStatusFilter.setMaxVisibleItems(18)
        self.cotStatusFilter.addItem("Tất cả trạng thái", "")
        self.cotStatusFilter.setEnabled(False)
        self.cotStatusFilter.currentIndexChanged.connect(self._select_cot_status)
        status_row.addWidget(self.cotStatusFilter)
        self.lblCotPercent = QLabel("")
        self.lblCotPercent.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        self.lblCotPercent.setWordWrap(True)
        status_row.addWidget(self.lblCotPercent, 1)
        cot_root.addLayout(status_row)

        self.cot_order_model = PandasModel()
        self.cotOrderTable = QTableView()
        self.cotOrderTable.setModel(self.cot_order_model)
        self.cotOrderTable.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        cot_root.addWidget(self.cotOrderTable, 1)

        self.lblCotOrderCount = QLabel("📊 Danh sách API: 0 dòng")
        self.lblCotOrderCount.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        cot_root.addWidget(self.lblCotOrderCount)

        self.mainTabs.addTab(self.cotTab, "⚡ COT Dashboard")

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

        # ===== Signal chung / COT =====
        self.btnLoginWMS.clicked.connect(self.login_wms)
        self.btnCotReloadList.clicked.connect(self.reload_cot_order_list)
        self.btnCotCopyList.clicked.connect(self.copy_cot_order_list)
        self.btnCotExportList.clicked.connect(self.export_cot_order_list)
        self.searchCotBox.textChanged.connect(self.search_cot_orders)
        self.cotService.currentTextChanged.connect(self._refresh_cot_picker)
        self.cotDate.dateChanged.connect(self._refresh_cot_picker)

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

        cot_shortcut_copy = QShortcut(QKeySequence.Copy, self.cotOrderTable)
        cot_shortcut_copy.activated.connect(self.copy_cot_order_list)

        # Không gọi WMS khi mở app, đổi nhóm hoặc đổi ngày.
        self._refresh_cot_picker()

    def login_wms(self):
        if self.login_thread is not None and self.login_thread.isRunning():
            QMessageBox.information(self, "WMS", "Cửa sổ đăng nhập WMS đang chạy.")
            return

        self.btnLoginWMS.setEnabled(False)
        self.set_banner_status(is_loading=True, custom_msg="⌛ Đang mở trình duyệt đăng nhập WMS...")

        self._login_outcome_received = False
        self.login_thread = WMSLoginThread()
        self.login_thread.progress.connect(self._on_login_progress)
        self.login_thread.login_success.connect(self._on_login_success)
        self.login_thread.login_failed.connect(self._on_login_failed)
        self.login_thread.finished.connect(self._on_login_thread_finished)
        self.login_thread.start()

    def _on_login_progress(self, message):
        self.set_banner_status(is_loading=True, custom_msg=message)

    def _on_login_thread_finished(self):
        self.btnLoginWMS.setEnabled(True)
        if not getattr(self, "_login_outcome_received", False):
            self.set_banner_status(
                is_loading=False, success=False,
                custom_msg="Đăng nhập WMS đã dừng. Bạn có thể bấm Đăng nhập lại."
            )

    def _on_login_success(self, cookie_str):
        self._login_outcome_received = True
        self.cot_cache.clear()
        self._refresh_cot_picker()
        self.config["wms_cookie"] = cookie_str
        saved = save_config(self.config)

        self.lblWMSState.setText("🟢 Đã đăng nhập WMS")
        if saved:
            msg = "✅ Đăng nhập WMS thành công và đã lưu phiên."
        else:
            msg = "✅ Đăng nhập WMS thành công, nhưng không thể lưu wms_config.json."
        self.set_banner_status(is_loading=False, success=True, custom_msg=msg)

    def _on_login_failed(self, err_msg):
        self._login_outcome_received = True
        self.lblWMSState.setText("🔴 Đăng nhập WMS chưa thành công")
        self.set_banner_status(
            is_loading=False,
            success=False,
            custom_msg=f"❌ Lỗi đăng nhập WMS: {err_msg}"
        )
        QMessageBox.warning(self, "Lỗi đăng nhập", err_msg)

    def _invalidate_wms_cookie(self, message):
        self.config["wms_cookie"] = ""
        save_config(self.config)
        self.lblWMSState.setText("🔴 Phiên WMS đã hết hạn")
        self.set_banner_status(is_loading=False, success=False, custom_msg=f"❌ {message}")
        QMessageBox.warning(self, "Phiên WMS", message)

    def build_cot_definitions(self):
        # Ngày COT là ngày kết thúc chu kỳ; mọi mốc đều theo giờ Việt Nam.
        day = self.cotDate.date().toPython()
        today = datetime(day.year, day.month, day.day, tzinfo=VN_TZ)
        yesterday = today - timedelta(days=1)
        now = datetime.now(VN_TZ)

        def at(base, hour, minute=0):
            return base.replace(hour=hour, minute=minute)

        def pick(key, group, button, beg, end, channels, handoff):
            return dict(key=key, group=group, button=button, label=f"{group} · {button}",
                        beg=beg, end=end, channels=channels, cutoff=False, handoff=handoff)

        def slot(label, beg, end, handoff):
            return dict(label=label, beg=beg, end=end, handoff=handoff)

        def intra(key, button, begin, finish, cutoff_hour, cutoff_minute, handoff, slots=None):
            # Giữ truy vấn Cut-Off đã chạy đúng để không lẫn kênh vận chuyển khác.
            # Purchase Time từ API quyết định đơn thuộc khung COT nào theo bảng mới.
            cut = at(today, cutoff_hour, cutoff_minute)
            return dict(key=key, group="Intra City", button=button, label=f"Intra City · {button}",
                        beg=cut - timedelta(minutes=1), end=cut + timedelta(minutes=1),
                        channels=None, cutoff=True, purchase_beg=begin, purchase_end=finish,
                        handoff=handoff, slots=slots or [])

        aha = ["50033", "50044"]
        sdd = ["50051"]
        defs = [
            intra("intra03", "COT 1 · 20:00–23:00", at(yesterday, 20), at(yesterday, 23), 3, 0,
                  "Cắt Pick 23:00 → Check 23:15 → Pack 00:00 → WIS 02:00"),
            intra("intra06", "COT 2 · 23:00–02:00", at(yesterday, 23), at(today, 2), 6, 0,
                  "Cắt Pick 02:00 → Check 02:15 → Pack 03:00 → WIS 05:00"),
            intra("intra20", "COT 3 · 02:00–16:00", at(today, 2), at(today, 16), 20, 0,
                  "Khung 02–05: WIS 06:00 · Khung 05–16: WIS 19:00", [
                      slot("02–05", at(today, 2), at(today, 5), "Cắt Pick 05:00 → Check 05:15 → Pack 05:30 → WIS 06:00"),
                      slot("05–16", at(today, 5), at(today, 16), "Cắt Pick 16:00 → Check 16:15 → Pack 16:30 → WIS 19:00"),
                  ]),
            intra("intra_end", "COT 4 · 16:00–20:00", at(today, 16), at(today, 20), 23, 50,
                  "Khung 16–18: WIS 19:00 · Khung 18–20: WIS 23:00", [
                      slot("16–18", at(today, 16), at(today, 18), "Cắt Pick 18:00 → Check 18:15 → Pack 18:30 → WIS 19:00"),
                      slot("18–20", at(today, 18), at(today, 20), "Cắt Pick 20:00 → Check 20:15 → Pack 20:30 → WIS 23:00"),
                  ]),
            pick("sdd18_04", "SDD", "18–04", at(yesterday, 18), at(today, 4), sdd,
                 "Cắt Pick 04:00 → Check 04:30 → Pack 05:00 → WIS 05:30"),
            pick("sdd04_09", "SDD", "04–09", at(today, 4), at(today, 9), sdd,
                 "Cắt Pick 09:00 → Check 09:15 → Pack 09:20 → WIS 09:45"),
            pick("sdd09_1330", "SDD", "09–13:30", at(today, 9), at(today, 13, 30), sdd,
                 "Cắt Pick 13:30 → Check 13:40 → Pack 13:55 → WIS 14:15"),
            pick("sdd1330_18", "SDD", "13:30–18", at(today, 13, 30), at(today, 18), sdd,
                 "Cắt Pick 18:00 → Check 21:00 → Pack 21:30 → WIS 22:00"),
            pick("aha10", "AhaMove", "18–08", at(yesterday, 18), at(today, 8), aha,
                 "Cắt Pick 08:00 → Check 08:30 → Pack 09:00 → WIS 09:30"),
            pick("aha15", "AhaMove", "08–13", at(today, 8), at(today, 13), aha,
                 "Cắt Pick 13:00 → Check 13:30 → Pack 14:00 → WIS 14:30"),
            pick("aha20", "AhaMove", "13–18", at(today, 13), at(today, 18), aha,
                 "Cắt Pick 18:00 → Check 18:30 → Pack 19:00 → WIS 19:30"),
            pick("bulky", "SPX Cồng kềnh", "17–17 (qua ngày)", at(yesterday, 17), at(today, 17), ["50025"],
                 "Cắt Pick 17:00 → Check 17:15 → Pack 17:20 → WIS 17:30"),
        ]
        defs[2]["cutoff_ranges"] = [
            (at(today, 5, 59), at(today, 6, 1)),
            (at(today, 19, 59), at(today, 20, 1)),
        ]
        defs[3]["cutoff_ranges"] = [
            (at(today, 19, 59), at(today, 20, 1)),
            (at(today, 23, 49), at(today, 23, 51)),
        ]
        end_day = min(today + timedelta(days=1), max(today, now))
        defs.extend([
            dict(key="ghn_total", group="GHN", button="Tổng GHN", label="GHN · Tổng", beg=today, end=end_day,
                 channels=None, cutoff=False, composite_channels=[["50032"], ["50011"]], handoff="GHN · Trong ngày đã chọn"),
            pick("ghn50032", "GHN", "Cồng kềnh", today, end_day, ["50032"], "GHN · Trong ngày đã chọn"),
            pick("ghn50011", "GHN", "Normal", today, end_day, ["50011"], "GHN · Trong ngày đã chọn"),
        ])
        return defs

    def _format_cot_range(self, cot_def):
        beg = cot_def.get("purchase_beg", cot_def["beg"])
        end = cot_def.get("purchase_end", cot_def["end"])
        return f"{beg:%d/%m %H:%M} → {end:%d/%m %H:%M}"

    def _clear_cot_button_row(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

    def _refresh_cot_picker(self, *args):
        self._reset_cot_status()
        self._cot_data_ready = False
        self._active_cot_request_id = None
        self._active_cot_cache_key = None
        self._pending_cot_list_request = None
        if self.cot_list_thread is not None and self.cot_list_thread.isRunning():
            self.cot_list_thread.requestInterruption()
        self.cot_definitions = self.build_cot_definitions()
        self.cot_definition_map = {d["key"]: d for d in self.cot_definitions}
        self.cot_current_selection = None
        self.cot_current_rows = []
        self.cot_current_df = pd.DataFrame()
        self.cot_current_total = 0
        self.searchCotBox.clear()
        self.cot_order_model.update_data(pd.DataFrame())
        self.lblCotOrderCount.setText("Chưa tải COT · Bấm nút để tải đúng khung cần xem.")
        self.lblCotSelection.setText("Chọn một nút COT để tải đơn của COT đó.")
        self.lblCotHandoff.setText("Intra City: theo Purchase Time. SDD / AhaMove / SPX: theo giờ cắt Pick.")
        self.cotSlotPanel.hide()
        self._clear_cot_button_row(self.cotButtonRow)
        if hasattr(self, "cotButtonGroup"):
            self.cotButtonGroup.deleteLater()
        self.cotButtonGroup = QButtonGroup(self)
        self.cot_buttons = {}
        for cot in self.cot_definitions:
            if cot["group"] != self.cotService.currentText():
                continue
            button = QPushButton(cot["button"])
            button.setCheckable(True)
            button.setProperty("cotChoice", True)
            button.setToolTip(f"{self._format_cot_range(cot)}\n{cot['handoff']}")
            button.clicked.connect(lambda checked=False, key=cot["key"]: self.request_cot_order_list(key, "total"))
            self.cotButtonGroup.addButton(button)
            self.cotButtonRow.addWidget(button, 1)
            self.cot_buttons[cot["key"]] = button
        for key, button in self.cot_metric_buttons.items():
            button.setText(f"{COT_METRIC_LABELS[key]}: —")
            button.setEnabled(False)
        self.set_banner_status(False, custom_msg="Chọn một COT để tải dữ liệu.")

    def _prepare_cot_selection(self, cot_def):
        self._reset_cot_status()
        self._cot_data_ready = False
        self.cot_active_slot = None
        self.cot_current_rows = []
        self.cot_current_df = pd.DataFrame()
        self.cot_current_total = 0
        self.cot_order_model.update_data(pd.DataFrame())
        if cot_def["key"] in self.cot_buttons:
            self.cot_buttons[cot_def["key"]].setChecked(True)
        self.lblCotSelection.setText(f"{cot_def['label']} | {self._format_cot_range(cot_def)}")
        self.lblCotHandoff.setText(cot_def["handoff"])
        self.cot_metric_buttons["total"].setChecked(True)
        for key, button in self.cot_metric_buttons.items():
            button.setText(f"{COT_METRIC_LABELS[key]}: —")
            button.setEnabled(False)
        self._clear_cot_button_row(self.cotSlotRow)
        if hasattr(self, "cotSlotGroup"):
            self.cotSlotGroup.deleteLater()
        self.cotSlotGroup = QButtonGroup(self)
        slots = cot_def.get("slots", [])
        if slots:
            self.cotSlotRow.addWidget(QLabel("Khung nhỏ:"))
            for index, label in [(None, "Toàn COT")] + [(i, sl["label"]) for i, sl in enumerate(slots)]:
                button = QPushButton(label)
                button.setCheckable(True)
                button.setProperty("cotChoice", True)
                button.setChecked(index is None)
                button.clicked.connect(lambda checked=False, i=index: self._select_cot_slot(i))
                self.cotSlotGroup.addButton(button)
                self.cotSlotRow.addWidget(button)
            self.cotSlotRow.addStretch()
        self.cotSlotPanel.setVisible(bool(slots))

    def _select_cot_slot(self, index):
        if not self.cot_current_selection:
            return
        self.cot_active_slot = index
        cot = self.cot_definition_map[self.cot_current_selection[0]]
        sl = cot["slots"][index] if index is not None else None
        self.lblCotHandoff.setText(sl["handoff"] if sl else cot["handoff"])
        span = dict(cot, purchase_beg=sl["beg"], purchase_end=sl["end"]) if sl else cot
        self.lblCotSelection.setText(f"{cot['label']} | {self._format_cot_range(span)}")
        self._show_cot_scope()

    def _select_cot_metric(self, metric_key):
        if not self.cot_current_selection:
            return
        self.cot_selected_status = ""
        self.cot_current_selection = (self.cot_current_selection[0], metric_key)
        self._show_cot_scope()

    def _reset_cot_status(self):
        self.cot_selected_status = ""
        self.cotStatusFilter.blockSignals(True)
        self.cotStatusFilter.clear()
        self.cotStatusFilter.addItem("Tất cả trạng thái", "")
        self.cotStatusFilter.blockSignals(False)
        self.cotStatusFilter.setEnabled(False)
        self.lblCotPercent.clear()
        self.lblCotPercent.hide()

    def _select_cot_status(self, index):
        if not self.cot_current_selection or not self._cot_data_ready:
            return
        self.cot_selected_status = self.cotStatusFilter.currentData() or ""
        self.cot_current_selection = (self.cot_current_selection[0], "total")
        self.searchCotBox.clear()
        self._show_cot_scope()

    def _show_cot_scope(self):
        if not self.cot_current_selection or not self._cot_data_ready:
            return
        cot_key, metric_key = self.cot_current_selection
        rows = _dedupe_cot_orders(self.cot_current_rows)
        if self.cot_active_slot is not None:
            slot = self.cot_definition_map[cot_key]["slots"][self.cot_active_slot]
            rows = _filter_purchase_window(rows, slot["beg"], slot["end"])
        counts = {}
        for row in rows:
            name = _order_status_name(row)
            counts[name] = counts.get(name, 0) + 1
        intra = self.cot_definition_map[cot_key]["group"] == "Intra City"
        total_valid = len(rows) - counts.get("Cancel", 0)
        unknown = any(name.startswith("Mã trạng thái ") or name == "Chưa có trạng thái" for name in counts)
        self.lblCotPercent.setVisible(intra)
        if intra:
            outbound = counts.get("Outbound", 0)
            if unknown:
                self.lblCotPercent.setText("Chưa tính %: API có mã trạng thái chưa xác định tên.")
            else:
                percent = outbound / total_valid * 100 if total_valid else 0
                self.lblCotPercent.setText(f"Tổng hợp lệ: {total_valid:,} · Outbound: {outbound:,} · Tỷ lệ: {percent:.2f}%")
        self.cotStatusFilter.blockSignals(True)
        self.cotStatusFilter.clear()
        self.cotStatusFilter.addItem(f"Tất cả trạng thái: {len(rows):,}", "")
        for name in COT_STATUS_ORDER + sorted(set(counts) - set(COT_STATUS_ORDER)):
            qty = counts.get(name, 0)
            label = f"{name}: {qty:,} đơn"
            if unknown and name in ("Cancel", "Pick Fail") and not qty:
                label = f"{name}: chưa xác định"
            elif intra and not unknown and name != "Cancel":
                pct = qty / total_valid * 100 if total_valid else 0
                label += f" ({pct:.2f}%)"
            self.cotStatusFilter.addItem(label, name)
        self.cotStatusFilter.setCurrentIndex(max(0, self.cotStatusFilter.findData(self.cot_selected_status)))
        self.cotStatusFilter.blockSignals(False)
        self.cotStatusFilter.setEnabled(True)
        for key, button in self.cot_metric_buttons.items():
            allowed = {COT_STATUS_NAMES[c] for c in COT_STATUS_GROUPS[key].split(",")}
            count = len(rows) if key == "total" else sum(_order_status_name(r) in allowed for r in rows)
            button.setText(f"{COT_METRIC_LABELS[key]}: {count:,}")
            button.setEnabled(True)
        self.cot_metric_buttons[metric_key].setChecked(True)
        if metric_key != "total":
            allowed = {COT_STATUS_NAMES[c] for c in COT_STATUS_GROUPS[metric_key].split(",")}
            rows = [r for r in rows if _order_status_name(r) in allowed]
        if self.cot_selected_status:
            rows = [r for r in rows if _order_status_name(r) == self.cot_selected_status]
        self._display_cot_orders(self._orders_to_dataframe(rows), len(rows))
        if self.searchCotBox.text():
            self.search_cot_orders()

    def _cot_cache_key(self, cot_def, metric_key):
        if cot_def.get("composite_channels"):
            channel_key = tuple(tuple(x) for x in cot_def["composite_channels"])
        else:
            channel_key = tuple(cot_def.get("channels") or [])
        return (
            cot_def["key"], metric_key,
            int(cot_def["beg"].timestamp()),
            int(cot_def["end"].timestamp()),
            bool(cot_def.get("cutoff")),
            channel_key,
            tuple((int(b.timestamp()), int(e.timestamp())) for b, e in cot_def.get("cutoff_ranges", [])),
        )

    def request_cot_order_list(self, row_key, metric_key="total", force=False):
        cot_def = self.cot_definition_map.get(row_key)
        if cot_def is None:
            return
        running = self.cot_list_thread is not None and self.cot_list_thread.isRunning()
        if running and self._active_cot_request_id is not None and self.cot_current_selection and self.cot_current_selection[0] == row_key:
            # Bấm nhiều lần (kể cả Tải lại) không tạo thêm yêu cầu đang tải.
            return
        self.cot_current_selection = (row_key, metric_key)
        self._prepare_cot_selection(cot_def)
        self.searchCotBox.clear()
        self._active_cot_request_id = None
        self._active_cot_cache_key = None
        self._pending_cot_list_request = None
        if running:
            self.cot_list_thread.requestInterruption()
        cookie_str = self.config.get("wms_cookie", "")
        if not cookie_str:
            QMessageBox.warning(self, "Chưa đăng nhập", "Vui lòng đăng nhập WMS trước.")
            return
        cache_key = self._cot_cache_key(cot_def, "total")
        if force:
            self.cot_cache.pop(cache_key, None)
        if cache_key in self.cot_cache:
            self.cot_current_rows = list(self.cot_cache[cache_key][0])
            self._cot_data_ready = True
            self._show_cot_scope()
            return
        if running:
            self._pending_cot_list_request = (row_key, metric_key, force)
            self.lblCotOrderCount.setText("⏳ Đang chuyển sang COT vừa chọn...")
            self.set_banner_status(True, custom_msg=f"⌛ Đang chuyển sang {cot_def['label']}...")
            return
        self._start_cot_order_thread(cot_def, "total", cache_key)

    def _start_cot_order_thread(self, cot_def, metric_key, cache_key):
        self._cot_request_serial += 1
        request_id = f"{cot_def['key']}|{self._cot_request_serial}"
        self._active_cot_request_id = request_id
        self._active_cot_cache_key = cache_key
        self.lblCotOrderCount.setText("⏳ Đang tải COT đã chọn...")
        self.set_banner_status(True, custom_msg=f"⌛ Đang tải {cot_def['label']}...")
        self.cot_list_thread = COTOrderListThread(
            request_id=request_id, cookie_str=self.config.get("wms_cookie", ""),
            cot_def=cot_def, metric_key="total", page_size=WMS_PAGE_SIZE,
        )
        self.cot_list_thread.list_ready.connect(self._on_cot_list_ready)
        self.cot_list_thread.progress.connect(self._on_cot_list_progress)
        self.cot_list_thread.auth_error.connect(self._on_cot_list_auth_error)
        self.cot_list_thread.error.connect(self._on_cot_list_error)
        self.cot_list_thread.finished.connect(self._on_cot_list_thread_finished)
        self.cot_list_thread.start()

    def _on_cot_list_progress(self, request_id, loaded, total):
        if request_id != self._active_cot_request_id:
            return
        self.lblCotOrderCount.setText(f"⏳ Đang tải: {loaded:,}/{total:,} đơn · {WMS_PAGE_SIZE} đơn/trang")

    def _on_cot_list_ready(self, request_id, rows, total_expected):
        if request_id != self._active_cot_request_id:
            return

        self.cot_current_rows = list(rows)
        self._cot_data_ready = True
        if self._active_cot_cache_key is not None:
            self.cot_cache[self._active_cot_cache_key] = (list(rows), int(total_expected))
        self._show_cot_scope()

    def _on_cot_list_auth_error(self, request_id, message):
        if request_id != self._active_cot_request_id:
            return
        self._invalidate_wms_cookie(message)

    def _on_cot_list_error(self, request_id, message):
        if request_id != self._active_cot_request_id:
            return
        self.cot_order_model.update_data(pd.DataFrame())
        self.lblCotOrderCount.setText(f"❌ Lỗi tải danh sách: {message}")
        self.set_banner_status(is_loading=False, success=False, custom_msg=f"❌ API WMS: {message}")

    def _on_cot_list_thread_finished(self):
        self._active_cot_request_id = None
        self._active_cot_cache_key = None

        pending = self._pending_cot_list_request
        self._pending_cot_list_request = None
        if not pending and not self._cot_data_ready:
            self.set_banner_status(False, success=not self.lblCotOrderCount.text().startswith("❌"), custom_msg=self.lblCotOrderCount.text())
        if pending:
            row_key, metric_key, force = pending
            QTimer.singleShot(
                0,
                lambda rk=row_key, mk=metric_key, f=force: self.request_cot_order_list(rk, mk, f)
            )

    def _orders_to_dataframe(self, rows):
        if not rows:
            return pd.DataFrame()

        friendly = {
            "_source_channel": "API Source Channel",
            "shopee_order_sn": "Shopee Order SN",
            "order_number": "WMS Order No",
            "order_status": "Order Status",
            "status": "Status",
            "whs_id": "WHS ID",
            "wave_type": "Wave Type",
            "sku_name": "SKU Name",
            "category": "Category",
            "picking_id": "Picking ID",
            "device_id": "Device ID",
            "lm_tracking_number": "LM Tracking Number",
            "channel_id": "Channel ID",
            "channel_name": "Channel",
            "buyer_name": "Buyer Name",
            "buyer_state": "Buyer State",
            "buyer_city": "Buyer City",
            "cut_off_time": "Cut-Off Time",
            "ctime": "Create Time",
            "purchase_time": "Purchase Time",
        }

        normalized = []
        for raw in rows:
            if not isinstance(raw, dict):
                normalized.append({"value": raw})
                continue

            out = {}
            for key, value in raw.items():
                display_key = friendly.get(str(key), str(key))
                if display_key in out:
                    display_key = f"{display_key} ({key})"

                if isinstance(value, (dict, list, tuple)):
                    try:
                        value = json.dumps(value, ensure_ascii=False)
                    except Exception:
                        value = str(value)
                out[display_key] = value
            out["Status"] = _order_status_name(raw)
            normalized.append(out)

        df = pd.DataFrame(normalized)

        preferred = [
            "Shopee Order SN", "WMS Order No", "Status", "Order Status",
            "Channel ID", "Channel", "API Source Channel",
            "WHS ID", "Wave Type", "Picking ID", "Device ID",
            "LM Tracking Number", "Buyer Name", "Buyer State", "Buyer City",
            "Purchase Time", "Cut-Off Time", "Create Time"
        ]
        ordered = [c for c in preferred if c in df.columns]
        ordered.extend(c for c in df.columns if c not in ordered)
        return df[ordered]

    def _display_cot_orders(self, df, total_expected):
        self.cot_current_df = df.copy()
        self.cot_current_total = int(total_expected)
        self.cot_order_model.update_data(df)

        loaded = len(df)
        if total_expected and loaded != total_expected:
            self.lblCotOrderCount.setText(
                f"📊 Danh sách API: {loaded:,} dòng | API báo tổng: {total_expected:,}"
            )
        else:
            self.lblCotOrderCount.setText(f"📊 Danh sách API: {loaded:,} dòng")

        self.set_banner_status(
            is_loading=False,
            success=True,
            custom_msg=f"✅ Đã tải danh sách API: {loaded:,} đơn."
        )

    def search_cot_orders(self):
        keyword = self.searchCotBox.text().strip()
        df = self.cot_current_df.copy()

        if df.empty:
            self.cot_order_model.update_data(pd.DataFrame())
            return

        if not keyword:
            self.cot_order_model.update_data(df)
            self.lblCotOrderCount.setText(
                f"📊 Danh sách API: {len(df):,} dòng"
                + (f" | API báo tổng: {self.cot_current_total:,}" if self.cot_current_total != len(df) else "")
            )
            return

        mask = pd.Series(False, index=df.index)
        for col in df.columns:
            mask |= df[col].astype(str).str.contains(keyword, case=False, na=False, regex=False)

        result = df[mask]
        self.cot_order_model.update_data(result, search_keyword=keyword)
        self.lblCotOrderCount.setText(
            f"🔍 Tìm thấy: {len(result):,}/{len(df):,} dòng"
        )

    def reload_cot_order_list(self):
        if not self.cot_current_selection:
            QMessageBox.information(self, "COT", "Hãy chọn một nút COT trước.")
            return
        row_key, metric_key = self.cot_current_selection
        self.request_cot_order_list(row_key, metric_key, force=True)

    def copy_cot_order_list(self):
        df = self.cot_order_model._data
        if df.empty:
            QMessageBox.information(self, "COT", "Chưa có danh sách đơn để copy.")
            return
        try:
            df.to_clipboard(sep="\t", index=False)
            QMessageBox.information(self, "COT", f"Đã copy {len(df):,} dòng.")
        except Exception as e:
            QMessageBox.warning(self, "COT", f"Không thể copy: {e}")

    def export_cot_order_list(self):
        df = self.cot_order_model._data
        if df.empty:
            QMessageBox.warning(self, "COT", "Chưa có danh sách đơn để xuất.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Xuất danh sách COT", "WMS_COT_Orders.xlsx", "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            df.to_excel(file_path, index=False)
            QMessageBox.information(
                self, "COT", f"Đã xuất {len(df):,} dòng ra:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "COT", f"Không thể xuất file: {e}")

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
        self._pending_cot_list_request = None

        # Yêu cầu các thread WMS dừng ở điểm an toàn giữa các request.
        for thread in (self.cot_list_thread, self.login_thread):
            if thread is not None and thread.isRunning():
                thread.requestInterruption()

        if self.loader_thread is not None and self.loader_thread.isRunning():
            if not self.loader_thread.wait(3000):
                self.set_banner_status(
                    is_loading=True,
                    custom_msg="⌛ Đang hoàn tất đọc dữ liệu trước khi đóng ứng dụng..."
                )
                event.ignore()
                return

        for thread in (self.cot_list_thread, self.login_thread):
            if thread is not None and thread.isRunning():
                if not thread.wait(3000):
                    self.set_banner_status(
                        is_loading=True,
                        custom_msg="⌛ Đang kết thúc tác vụ WMS trước khi đóng ứng dụng..."
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
