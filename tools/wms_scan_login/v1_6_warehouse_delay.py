"""WMS Scan Login v1.6 — per-lane warehouse selection, delayed native zoom."""
from pathlib import Path
root=Path(__file__).resolve().parents[2]/"scan_build"

def change(file,old,new):
    p=root/file
    s=p.read_text(encoding="utf-8")
    if s.count(old)!=1:
        raise AssertionError(f"{file}: patch marker mismatch ({s.count(old)}): {old[:65]}")
    p.write_text(s.replace(old,new),encoding="utf-8")

change("settings.py", '    "pack_station_id": "",\n',
       '    "pack_station_id": "",\n    "check_warehouse": "",\n    "pack_warehouse": "",\n')
change("settings.py", "def read_config() -> dict:\n", '''def validate_warehouse(value: str) -> str:
    """Blank keeps current WMS warehouse; nonblank uses an exact VN code."""
    import re
    value=" ".join(str(value or "").strip().upper().split())
    if not value:
        return ""
    m=re.fullmatch(r"VN\s*-\s*([A-Z0-9]{2,12})",value)
    if not m:
        raise ValueError("Tên kho phải có dạng VN - VNA, VN - VNG, VN - VNN...")
    return "VN - "+m.group(1)


def read_config() -> dict:
''')
change("settings.py",'        return config\n    except (FileNotFoundError, ValueError, OSError):',
'''        for k in ("check_warehouse","pack_warehouse"):
            try:
                config[k]=validate_warehouse(config.get(k,""))
            except ValueError:
                config[k]=""
        return config
    except (FileNotFoundError, ValueError, OSError):''')
change("settings.py", '    values["chrome_zoom_percent"] = validate_zoom(values["chrome_zoom_percent"])\n',
'''    values["chrome_zoom_percent"] = validate_zoom(values["chrome_zoom_percent"])
    for k in ("check_warehouse","pack_warehouse"):
        values[k]=validate_warehouse(values[k])
''')
change("automation.py","from settings import decrypt_password, validate_station_id, validate_zoom",
                   "from settings import decrypt_password, validate_station_id, validate_zoom, validate_warehouse")
code=r'''
def _warehouse_elements(driver):
    """Find compact exact warehouse labels via one DOM traversal."""
    elements=driver.execute_script("""
        return [...document.querySelectorAll('button,span,div,li,a,[role=option]')]
            .filter(el=>{
                const t=(el.textContent||'').replace(/\s+/g,' ').trim();
                const r=el.getBoundingClientRect();
                return /^VN\s*-\s*[A-Z0-9]{2,12}$/i.test(t)
                    && r.x>=0 && r.x<430 && r.y>=0 && r.y<900
                    && r.width>1 && r.height>5 && el.getClientRects().length;
            }).slice(0,80);
    """)
    for e in elements:
        try:
            if not e.is_displayed() or not e.is_enabled(): continue
            raw=(e.get_attribute("textContent") or "").strip()
            label=validate_warehouse(raw)
            yield e,label
        except (WebDriverException,ValueError):
            continue

def _current_warehouse(driver):
    # Sidebar title appears above its expanded option list.
    choices=[]
    for e,label in _warehouse_elements(driver):
        try:
            r=e.rect
            if 0<=r["x"]<=400 and 40<=r["y"]<=460:
                choices.append((r["y"],r["width"],e,label))
        except (WebDriverException,KeyError):
            pass
    if not choices:return None
    choices.sort(key=lambda item:(item[0],item[1]))
    return choices[0][2:]

def _select_warehouse(driver,requested,status):
    requested=validate_warehouse(requested)
    if not requested:return False
    if _host(driver.current_url)!=WMS_HOST:
        raise AutomationError("Không thể chọn kho khi chưa ở WMS.")
    try:
        current,name=WebDriverWait(driver,25,poll_frequency=.4).until(
            lambda d:_current_warehouse(d))
    except TimeoutException as exc:
        raise AutomationError("Không tìm thấy danh sách chọn kho ở góc trái WMS.") from exc
    if name==requested:
        status(f"Đã ở đúng kho {requested}.")
        return False
    try:
        current.click()
    except WebDriverException as exc:
        raise AutomationError("Không mở được danh sách kho WMS.") from exc
    try:
        option=WebDriverWait(driver,15,poll_frequency=.4).until(lambda d:next(
            (e for e,label in _warehouse_elements(d)
             if label==requested and e.id != current.id),None))
    except TimeoutException as exc:
        raise AutomationError(f"Không thấy kho {requested} hoặc tài khoản không được phép chọn.") from exc
    try:
        option.click()
    except WebDriverException as exc:
        raise AutomationError(f"Không chọn được kho {requested}.") from exc
    try:
        WebDriverWait(driver,25,poll_frequency=.5).until(
            lambda d:(_current_warehouse(d) or (None,None))[1]==requested)
    except TimeoutException as exc:
        raise AutomationError(f"WMS chưa xác nhận chuyển kho {requested}; dừng trước khi nhập mã trạm.") from exc
    status(f"Đã chuyển kho: {requested}.")
    return True
'''
change("automation.py","\nclass SessionManager:\n","\n"+code+"\nclass SessionManager:\n")
old='''            # Set zoom before selecting the scan field so Ctrl+- cannot be
            # interpreted as an accidental scanner input by the WMS page.
            zoom_percent = cfg.get("chrome_zoom_percent", 75)
            zoom_done = _set_browser_zoom(driver, zoom_percent, lambda msg: status(f"{lane}: {msg}"))
            station_code = cfg.get("check_station_id" if lane == "CHECK" else "pack_station_id", "")
            if station_code and station_code.strip():
                try:
                    _enter_station(driver,station_code,lambda msg: status(f"{lane}: {msg}"))
                except (AutomationError,WebDriverException,ValueError) as exc:
                    # A station failure must not undo the successful login.
                    status(f"{lane}: Đã mở trang, nhưng chưa nhập được mã trạm: {exc}")
                    return
            status(f"{lane}: Đăng nhập thành công và đã mở trang {lane}" +
                   (f" · Zoom {zoom_percent}%." if zoom_done else "."))'''
new='''            # Choose the warehouse on the actual work tab. Some versions of
            # WMS render the sidebar only after this tab has loaded.
            warehouse=cfg.get("check_warehouse" if lane=="CHECK" else "pack_warehouse","")
            if warehouse:
                changed=_select_warehouse(driver,warehouse,lambda msg:status(f"{lane}: {msg}"))
                if changed:
                    # WMS can navigate after switching. Restore the work route.
                    driver.get(target)
                    try:
                        WebDriverWait(driver,35,poll_frequency=.5).until(
                            lambda d:d.current_url.split("?",1)[0].rstrip("/")==target.rstrip("/"))
                    except TimeoutException as exc:
                        raise AutomationError("Không thể mở lại trang sau khi chuyển kho.") from exc
                if (_current_warehouse(driver) or (None,None))[1]!=validate_warehouse(warehouse):
                    raise AutomationError("Chưa xác minh được kho đã chọn; không tự nhập mã trạm.")
            station_code=cfg.get("check_station_id" if lane=="CHECK" else "pack_station_id","")
            if station_code and station_code.strip():
                try:
                    _enter_station(driver,station_code,lambda msg:status(f"{lane}: {msg}"))
                except (AutomationError,WebDriverException,ValueError) as exc:
                    status(f"{lane}: Đã mở trang, nhưng chưa nhập được mã trạm: {exc}")
                    return
            # Zoom last: wait five seconds after station+Enter (or page load).
            status(f"{lane}: Đợi 5 giây rồi tự điều chỉnh Zoom...")
            time.sleep(5)
            zoom_percent=cfg.get("chrome_zoom_percent",75)
            zoom_done=_set_browser_zoom(driver,zoom_percent,lambda msg:status(f"{lane}: {msg}"))
            status(f"{lane}: Đăng nhập thành công" +
                   (f" · Kho {warehouse}" if warehouse else " · Giữ kho hiện tại") +
                   (f" · Zoom {zoom_percent}%." if zoom_done else "."))'''
p=root/"automation.py"
a=p.read_text(encoding="utf-8")
start=a.index("            # Set zoom before selecting the scan field")
end=a.index("        except AutomationError:", start)
assert end>start
p.write_text(a[:start]+new+a[end:], encoding="utf-8")
change("main.py","validate_station_id, validate_zoom, ZOOM_PRESETS, write_config)",
                 "validate_station_id, validate_zoom, validate_warehouse, ZOOM_PRESETS, write_config)")
change("main.py",'        self.station_labels = {}\n',
                 '        self.station_labels = {}\n        self.warehouse_labels = {}\n')
change("main.py",'''        self.station_labels[lane] = station
        self._refresh_station(lane)
''','''        self.station_labels[lane] = station
        wh = label(note, "", 9, color=MUTED)
        wh.pack(anchor="w", pady=(4, 0))
        self.warehouse_labels[lane] = wh
        self._refresh_station(lane)
''')
change("main.py",'''        self.station_labels[lane].configure(
            text=f"●  Trạm {station}  ·  Tự nhập + Enter" if station else "○  Không tự nhập mã trạm")''','''        self.station_labels[lane].configure(
            text=f"●  Trạm {station}  ·  Tự nhập + Enter" if station else "○  Không tự nhập mã trạm")
        warehouse=self.cfg.get("check_warehouse" if lane=="CHECK" else "pack_warehouse","")
        self.warehouse_labels[lane].configure(text=f"Kho: {warehouse}" if warehouse else "Kho: giữ nguyên")''')
change("main.py", '        advanced = tk.Frame(panel, bg=WHITE)\n',
                 '        advanced = tk.Frame(panel, bg=WHITE)\n        warehouse_panel = tk.Frame(panel, bg=WHITE)\n')
change("main.py", '        label(advanced, "ĐƯỜNG DẪN WMS", 10, "bold", TEXT).pack(anchor="w", pady=(0, 12))',
'''        label(warehouse_panel, "KHO MẶC ĐỊNH", 11, "bold", TEXT).pack(anchor="w", pady=(0, 12))
        label(warehouse_panel, "Để trống để giữ nguyên kho trên WMS. Nhập đúng tên kho mà tài khoản được phép sử dụng.",
              10, color=MUTED, wraplength=620, justify="left").pack(anchor="w", pady=(0, 20))
        warehouse_vars={}
        for lane,key in (("CHECK","check_warehouse"),("PACK","pack_warehouse")):
            label(warehouse_panel, f"Kho {lane}", 10, "bold", TEXT).pack(anchor="w", pady=(0, 6))
            var=tk.StringVar(value=self.cfg.get(key,""))
            ttk.Combobox(warehouse_panel, textvariable=var, state="normal",
                         values=("", "VN - VNA", "VN - VNG", "VN - VNN"),
                         font=(FONT, 11)).pack(fill="x", ipady=6, pady=(0, 17))
            warehouse_vars[key]=var
        label(warehouse_panel, "Nếu không tìm thấy kho hoặc chưa xác nhận chuyển kho, tool sẽ không tự nhập mã trạm.",
              9, color=MUTED, wraplength=620, justify="left").pack(anchor="w")

        label(advanced, "ĐƯỜNG DẪN WMS", 10, "bold", TEXT).pack(anchor="w", pady=(0, 12))''')
change("main.py",'''            for frame in (basic, advanced):
                frame.pack_forget()
            (basic if which == "basic" else advanced).pack(fill="both", expand=True)''','''            for frame in (basic, advanced, warehouse_panel):
                frame.pack_forget()
            {"basic":basic,"advanced":advanced,"warehouse":warehouse_panel}[which].pack(fill="both", expand=True)''')
change("main.py",'''        for key, title in (("basic", "Cơ bản"), ("advanced", "Nâng cao")):''',
                 '''        for key, title in (("basic", "Cơ bản"), ("warehouse", "Chọn kho"), ("advanced", "Nâng cao")):''')
change("main.py",'''                new["chrome_zoom_percent"] = validate_zoom(zoom_var.get())''',
'''                for key,var in warehouse_vars.items():
                    new[key]=validate_warehouse(var.get())
                new["chrome_zoom_percent"] = validate_zoom(zoom_var.get())''')
tests=root/"tests"/"test_warehouse.py"
tests.write_text('''import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from settings import DEFAULTS,validate_warehouse
class WarehouseTests(unittest.TestCase):
    def test_defaults_blank(self):
        self.assertEqual(DEFAULTS["check_warehouse"],"")
        self.assertEqual(DEFAULTS["pack_warehouse"],"")
    def test_valid_names(self):
        self.assertEqual(validate_warehouse(" vn-vnn "),"VN - VNN")
        self.assertEqual(validate_warehouse("VN - VNA"),"VN - VNA")
        self.assertEqual(validate_warehouse(""),"")
    def test_invalid_names(self):
        for value in ("Admin Portal","VN - Region Dashboard","VN - VNA and more"):
            with self.assertRaises(ValueError):
                validate_warehouse(value)
''',encoding="utf-8")
print("v1.6 patch successfully applied")
