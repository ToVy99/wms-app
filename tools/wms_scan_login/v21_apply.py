"""WMS Auto Login v2.1: compact CHECK/PACK tabs, cancel, session lifecycle."""
from pathlib import Path
root=Path("scan_build")
def mutate(name, edits):
    p=root/name
    txt=p.read_text(encoding="utf-8")
    for old,new in edits:
        if txt.count(old)!=1:
            raise RuntimeError(f"{name} expected 1 occurrence, got {txt.count(old)}: {old[:80]!r}")
        txt=txt.replace(old,new)
    p.write_text(txt,encoding="utf-8")

mutate("settings.py",[
    ('    "open_separate_windows": True,\n',
     '    "open_separate_windows": True,\n    "close_old_chrome_on_new_login": True,\n')
])
mutate("automation.py",[
('''    def __init__(self):
        self.sessions = {}  # CHECK/PACK -> (WebDriver, temporary profile directory)

    def _close(self, lane):
        old = self.sessions.pop(lane, None)
        if old:
            driver, profile = old
            try:
                driver.quit()
            except Exception:
                pass
            shutil.rmtree(profile, ignore_errors=True)

    def close_all(self):
        for lane in list(self.sessions):
            self._close(lane)
''',
'''    def __init__(self):
        self.sessions = {}  # unique id -> (lane, WebDriver, temporary profile)
        self._counter = 0

    def _dispose(self, key):
        record = self.sessions.pop(key, None)
        if record is None:
            return
        _lane, driver, profile = record
        try:
            driver.quit()  # Only close tool-managed Selenium sessions.
        except Exception:
            pass
        shutil.rmtree(profile, ignore_errors=True)

    def _close(self, lane):
        for key, record in list(self.sessions.items()):
            if record[0] == lane:
                self._dispose(key)

    def close_all(self):
        for key in list(self.sessions):
            self._dispose(key)
'''),
('''        if not cfg.get("open_separate_windows", True):
            self.close_all()
        else:
            self._close(lane)
''',
'''        # The new setting is authoritative: when OFF, preserve all old
        # tool-managed browsers including previous logins to the same lane.
        if cfg.get("close_old_chrome_on_new_login", True):
            status("Đóng Chrome cũ của tool trước khi đăng nhập mới...")
            self.close_all()
'''),
('''        self.sessions[lane] = (driver, profile)''',
'''        self._counter += 1
        self.sessions[self._counter] = (lane, driver, profile)'''),
])
mutate("main.py",[
('self.root.title("WMS Scan Login  •  CHECK / PACK")',
 'self.root.title("WMS Auto Login  •  CHECK / PACK")'),
('''        self.root.geometry("940x650")
        self.root.minsize(760, 595)''',
'''        self.root.geometry("550x670")
        self.root.minsize(490, 645)'''),
('        self.scan_focus = "CHECK"\n','        self.scan_focus = "CHECK"\n        self.current_lane = "CHECK"\n'),
('        header = tk.Frame(self.root, bg=NAVY, padx=26, pady=19)',
 '        header = tk.Frame(self.root, bg=NAVY, padx=22, pady=13)'),
('label(title, "Đăng nhập nhanh", 20, "bold", WHITE, NAVY)',
 'label(title, "Đăng nhập nhanh", 18, "bold", WHITE, NAVY)'),
('''        label(header, "Chọn vị trí làm việc, quét tài khoản và nhấn Enter. Chrome sẽ mở đúng trang WMS.",
              10, color="#C6D3E2", bg=NAVY).pack(anchor="w", pady=(12, 0))''',
'''        label(header, "CHECK hoặc PACK · Quét mã nhân viên để đăng nhập WMS",
              9, color="#C6D3E2", bg=NAVY).pack(anchor="w", pady=(6, 0))'''),
('''        body = tk.Frame(self.root, bg=BG, padx=24, pady=20)
        body.pack(fill="both", expand=True)
        cards = tk.Frame(body, bg=BG)
        cards.pack(fill="both", expand=True)
        cards.grid_columnconfigure(0, weight=1, uniform="lane")
        cards.grid_columnconfigure(1, weight=1, uniform="lane")
        cards.grid_rowconfigure(0, weight=1)
        self.entries = {}
        self.buttons = {}
        self.station_labels = {}
        self.warehouse_labels = {}
        self._lane(cards, "CHECK", "Kiểm hàng", BLUE, 0)
        self._lane(cards, "PACK", "Đóng gói", PURPLE, 1)''',
'''        body = tk.Frame(self.root, bg=BG, padx=18, pady=10)
        body.pack(fill="both", expand=True)
        switch = tk.Frame(body, bg=BG)
        switch.pack(fill="x", pady=(0, 10))
        self.lane_tabs = {}
        for lane, color, title in (("CHECK", BLUE, "✓  CHECK  •  Kiểm hàng"),
                                   ("PACK", PURPLE, "▣  PACK  •  Đóng gói")):
            tab = button(switch, title, lambda selected=lane: self._switch_lane(selected),
                         WHITE, TEXT, size=11, pady=10)
            tab.pack(side="left", fill="x", expand=True,
                     padx=(0, 5) if lane == "CHECK" else (5, 0))
            self.lane_tabs[lane] = tab
        cards = tk.Frame(body, bg=BG)
        cards.pack(fill="both", expand=True)
        cards.grid_columnconfigure(0, weight=1)
        cards.grid_rowconfigure(0, weight=1)
        self.entries = {}
        self.buttons = {}
        self.station_labels = {}
        self.warehouse_labels = {}
        self.lane_cards = {}
        self._lane(cards, "CHECK", "Kiểm hàng", BLUE, 0)
        self._lane(cards, "PACK", "Đóng gói", PURPLE, 1)
        self._switch_lane("CHECK", focus=False)'''),
('        footer.pack(fill="x", pady=(17, 0))','        footer.pack(fill="x", pady=(8, 0))'),
('''        self.pause_button = button(actions, "⏸ Tạm dừng", self._pause_workflow,
                                   "#E6A33A", size=9, padx=12, pady=8)
        self.resume_button = button(actions, "▶ Tiếp tục", self._resume_workflow,
                                    BLUE, size=9, padx=12, pady=8)
        self.stop_button = button(actions, "■ Dừng", self._stop_workflow,
                                  DANGER, size=9, padx=12, pady=8)
        for item in (self.pause_button, self.resume_button, self.stop_button):
            item.pack(side="left", padx=(0, 8))
            item.configure(state="disabled")''',
'''        self.pause_button = button(actions, "⏸ Tạm dừng", self._pause_workflow,
                                   "#E6A33A", size=9, padx=11, pady=10)
        self.resume_button = button(actions, "▶ Tiếp tục", self._resume_workflow,
                                    BLUE, size=9, padx=11, pady=10)
        self.stop_button = button(actions, "✕ HỦY / DỪNG", self._stop_workflow,
                                  DANGER, size=10, padx=18, pady=10)
        self.pause_button.pack(side="left", padx=(0, 5))
        self.resume_button.pack(side="left", padx=(0, 5))
        self.stop_button.pack(side="right")
        for item in (self.pause_button, self.resume_button, self.stop_button):
            item.configure(state="disabled")'''),
('        self.status_text = label(inset, "", 10, color=TEXT, wraplength=790, justify="left")',
 '        self.status_text = label(inset, "", 9, color=TEXT, wraplength=425, justify="left")'),
('''        label(body, "SÚNG SCAN: gửi Enter sau mã   •   Mã trạm được tự nhập nếu đã cài đặt", 9,
              color=MUTED, bg=BG).pack(anchor="w", pady=(8, 0))''',
'''        label(body, "Súng quét: mã + Enter  ·  Có mã trạm sẽ tự gửi Enter", 9,
              color=MUTED, bg=BG).pack(anchor="w", pady=(5, 0))'''),
('''        outer.grid(row=0, column=column, sticky="nsew",
                   padx=(0, 9) if column == 0 else (9, 0))''',
'''        outer.grid(row=0, column=0, sticky="nsew")
        self.lane_cards[lane] = outer'''),
('        inside = tk.Frame(card, bg=WHITE, padx=21, pady=17)',
 '        inside = tk.Frame(card, bg=WHITE, padx=20, pady=11)'),
('        label(inside, "MÃ TÀI KHOẢN", 9, "bold", MUTED).pack(anchor="w", pady=(21, 7))',
 '        label(inside, "MÃ TÀI KHOẢN", 9, "bold", MUTED).pack(anchor="w", pady=(12, 5))'),
('        action.pack(fill="x", pady=(14, 0))','        action.pack(fill="x", pady=(9, 0))'),
('        note.pack(side="bottom", fill="x", pady=(18, 0))',
 '        note.pack(side="bottom", fill="x", pady=(9, 0))'),
('    def _refresh_station(self, lane):',
'''    def _switch_lane(self, lane, focus=True):
        """Display only selected lane and prevent mid-login lane changes."""
        if lane not in ("CHECK", "PACK"):
            return False
        if self.busy:
            self._set_status("Đang chạy tự động. Hãy HỦY / DỪNG trước khi chuyển CHECK / PACK.")
            return False
        self.current_lane = lane
        self.scan_focus = lane
        for which, card in self.lane_cards.items():
            if which == lane:
                card.grid()
            else:
                card.grid_remove()
        for which, tab in self.lane_tabs.items():
            selected = which == lane
            tab.configure(bg=(BLUE if which == "CHECK" else PURPLE) if selected else WHITE,
                          fg=WHITE if selected else TEXT,
                          relief="sunken" if selected else "flat")
        if focus:
            self.entries[lane].focus_set()
        return True

    def _refresh_station(self, lane):'''),
('''        self.busy = True
        from control import WorkflowControl''',
'''        if lane != self.current_lane:
            self._set_status("Chọn tab CHECK / PACK tương ứng trước khi đăng nhập.")
            return
        self.busy = True
        for item in self.lane_tabs.values():
            item.configure(state="disabled")
        from control import WorkflowControl'''),
('''                    for item in self.buttons.values():
                        item.configure(state="normal")''',
'''                    for item in self.buttons.values():
                        item.configure(state="normal")
                    for item in self.lane_tabs.values():
                        item.configure(state="normal")
                    if not self.shutdown_started:
                        self.entries[self.current_lane].focus_set()'''),
('''        separate = tk.BooleanVar(value=self.cfg["open_separate_windows"])
        on_top = tk.BooleanVar(value=self.cfg["keep_on_top"])
        for text, var in (("Mỗi vị trí CHECK / PACK dùng một cửa sổ Chrome riêng", separate),
                          ("Giữ cửa sổ tool luôn ở trên cùng", on_top)):''',
'''        on_top = tk.BooleanVar(value=self.cfg["keep_on_top"])
        close_previous = tk.BooleanVar(value=self.cfg.get("close_old_chrome_on_new_login", True))
        tk.Checkbutton(basic, text="Đóng Chrome cũ khi đăng nhập tài khoản mới",
                       variable=close_previous, bg=WHITE, fg=TEXT,
                       font=(FONT, 10, "bold"), relief="flat", activebackground=WHITE,
                       anchor="w").pack(fill="x", pady=(0, 2))
        label(basic, "Bật: đóng Chrome của tool trước khi mở phiên mới.\\n"
              "Tắt: giữ Chrome cũ, chỉ mở thêm Chrome mới.",
              9, color=MUTED, justify="left").pack(anchor="w", pady=(0, 5))
        for text, var in (("Giữ cửa sổ tool luôn ở trên cùng", on_top),):'''),
('''                new["open_separate_windows"] = separate.get()
                new["keep_on_top"] = on_top.get()''',
'''                new["close_old_chrome_on_new_login"] = close_previous.get()
                new["keep_on_top"] = on_top.get()'''),
('''        win.geometry("750x690")
        win.minsize(650, 615)''',
'''        win.geometry("735x710")
        win.minsize(650, 650)'''),
('''        assert all(app.entries[l].winfo_exists() for l in ("CHECK", "PACK"))''',
'''        assert all(app.entries[l].winfo_exists() for l in ("CHECK", "PACK"))
        assert app.current_lane == "CHECK"
        assert app.lane_cards["CHECK"].winfo_ismapped()
        assert not app.lane_cards["PACK"].winfo_ismapped()
        assert app._switch_lane("PACK")
        root.update()
        assert app.lane_cards["PACK"].winfo_ismapped()
        assert not app.lane_cards["CHECK"].winfo_ismapped()
        assert app._switch_lane("CHECK")
        root.update()
        assert "HỦY" in app.stop_button.cget("text")'''),
])
(root/"tests"/"test_v21_sessions.py").write_text('''import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from settings import DEFAULTS
from automation import SessionManager
class SessionTests(unittest.TestCase):
    def test_default_close_enabled(self):
        self.assertTrue(DEFAULTS["close_old_chrome_on_new_login"])
    def test_close_managed_sessions(self):
        m=SessionManager()
        a,b=Mock(),Mock()
        m.sessions={1:("CHECK",a,Path("m1")),2:("PACK",b,Path("m2"))}
        with patch("automation.shutil.rmtree"):
            m.close_all()
        self.assertFalse(m.sessions)
        a.quit.assert_called_once()
        b.quit.assert_called_once()
    def test_multiple_same_lane_preserved_until_explicit_close(self):
        m=SessionManager()
        a,b=Mock(),Mock()
        m.sessions={1:("CHECK",a,Path("m1")),2:("CHECK",b,Path("m2"))}
        with patch("automation.shutil.rmtree"):
            m._close("CHECK")
        a.quit.assert_called_once()
        b.quit.assert_called_once()
''',encoding="utf-8")
print("Applied v2.1: compact tab UI, immediate stop, managed Chrome lifecycle setting")
