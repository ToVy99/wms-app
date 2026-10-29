"""WMS Scan Login v1.3: station defaults, auto scan and Enter."""
from pathlib import Path
root=Path(__file__).resolve().parents[2] / "scan_build"
assert (root/"automation.py").is_file()
def change(path,old,new):
    p=root/path
    s=p.read_text(encoding="utf-8")
    assert s.count(old)==1,(path,old[:70],s.count(old))
    p.write_text(s.replace(old,new),encoding="utf-8")

change("settings.py", '    "keep_on_top": False,\n',
       '    "keep_on_top": False,\n    "check_station_id": "SS00085",\n    "pack_station_id": "",\n')
change("settings.py", '\ndef read_config() -> dict:\n',
''' 
def validate_station_id(code: str) -> str:
    import re
    code=code.strip().upper()
    if code and not re.fullmatch(r"[A-Z0-9_-]{1,32}",code):
        raise ValueError("Mã trạm chỉ gồm chữ/số/-/_ và tối đa 32 ký tự.")
    return code

def read_config() -> dict:
''')
change("automation.py","from selenium import webdriver\n",
       "from selenium import webdriver\nfrom selenium.webdriver.common.action_chains import ActionChains\n")
change("automation.py","from settings import decrypt_password\n",
       "from settings import decrypt_password, validate_station_id\n")
functions='''
def _station_field(driver):
    # Never type the station ID into an unrelated WMS field.
    for css in ("input[placeholder*='station' i]",
                "input[aria-label*='station' i]",
                "input[name*='station' i]",
                "input[id*='station' i]",
                "textarea[placeholder*='station' i]"):
        found=_lookup(driver,css)
        if found is not None:
            return found
    return None

def _station_prompt(driver):
    try:
        matches=driver.find_elements(By.XPATH,
            "//*[contains(translate(normalize-space(text()), "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), "
            "'scan/input station id')]")
        return next(_visible(matches),None)
    except WebDriverException:
        return None

def _enter_station(driver, station_code: str, status: Callable[[str], None]):
    station_code=validate_station_id(station_code)
    if not station_code:
        return
    status("Đang tìm Scan/Input Station ID...")
    try:
        WebDriverWait(driver,24,poll_frequency=0.4).until(
            lambda d: _station_field(d) or _station_prompt(d))
    except TimeoutException as exc:
        raise AutomationError("Không tìm thấy ô nhập mã trạm.") from exc
    field=_station_field(driver)
    if field is None:
        prompt=_station_prompt(driver)
        if prompt is None:
            raise AutomationError("Không tìm thấy vị trí quét mã trạm.")
        prompt.click()
        # On some WMS screens clicking the scan banner opens an input field.
        try:
            field=WebDriverWait(driver,3,poll_frequency=0.25).until(
                lambda d: _station_field(d))
        except TimeoutException:
            field=None
    if field is not None:
        _send_text(field,station_code)
        field.send_keys(Keys.ENTER)
    else:
        # WMS may listen for scanner input on the focused page instead.
        ActionChains(driver).send_keys(station_code).send_keys(Keys.ENTER).perform()
    status("Đã gửi mã trạm "+station_code+" + Enter.")

'''
change("automation.py", "\nclass SessionManager:\n", functions+"\nclass SessionManager:\n")
change("automation.py",'            status(f"{lane}: Đăng nhập thành công và đã mở trang {lane}.")',
'''            code=cfg.get("check_station_id" if lane=="CHECK" else "pack_station_id","")
            if code and code.strip():
                try:
                    _enter_station(driver,code,lambda msg: status(f"{lane}: {msg}"))
                except (AutomationError,WebDriverException,ValueError) as exc:
                    status(f"{lane}: Đã mở trang, nhưng chưa nhập được mã trạm: {exc}")
                    return
            status(f"{lane}: Đăng nhập thành công và đã mở trang {lane}.")''')
change("main.py","read_config, validate_wms_url, write_config",
       "read_config, validate_wms_url, validate_station_id, write_config")
change("main.py",'        win.geometry("740x515")','        win.geometry("740x620")')
change("main.py",'        ttk.Label(panel, text="Mật khẩu dùng chung (để trống = giữ mật khẩu đã lưu)").pack(anchor="w")',
'''        station_row=ttk.Frame(panel)
        station_row.pack(fill="x",pady=(3,8))
        station_vars={}
        for i,lane in enumerate(("CHECK","PACK")):
            station_row.grid_columnconfigure(i,weight=1)
            cell=ttk.Frame(station_row)
            cell.grid(row=0,column=i,sticky="ew",padx=(0,8) if i==0 else (8,0))
            key="check_station_id" if lane=="CHECK" else "pack_station_id"
            ttk.Label(cell,text=f"Mã trạm {lane} (để trống = không nhập)").pack(anchor="w")
            var=tk.StringVar(value=self.cfg.get(key,""))
            ttk.Entry(cell,textvariable=var).pack(fill="x")
            station_vars[key]=var
        ttk.Label(panel, text="Mật khẩu dùng chung (để trống = giữ mật khẩu đã lưu)").pack(anchor="w")''')
change("main.py",'                updated["open_separate_windows"] = separate.get()',
'''                for key,var in station_vars.items():
                    updated[key]=validate_station_id(var.get())
                updated["open_separate_windows"] = separate.get()''')
test=root/"tests"/"test_station.py"
test.write_text('''import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from settings import DEFAULTS,validate_station_id
class StationTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(DEFAULTS["check_station_id"],"SS00085")
        self.assertEqual(DEFAULTS["pack_station_id"],"")
    def test_validation(self):
        self.assertEqual(validate_station_id("ss00085"),"SS00085")
        self.assertEqual(validate_station_id(""),"")
        with self.assertRaises(ValueError):
            validate_station_id("bad station")
''',encoding="utf-8")
# The v1.2 frozen exe self-test already launches Selenium/Chrome.
change("main.py",'            assert driver.title == "WMS smoke test"\n',
'''            assert driver.title == "WMS smoke test"
            from urllib.parse import quote
            from automation import _enter_station
            html=("<html><body><span>Scan/Input Station ID</span>"
                  "<input id='station' placeholder='Station ID'>"
                  "<b id='received'></b><script>"
                  "document.getElementById('station').addEventListener('keydown',"
                  "function(e){if(e.key==='Enter'){"
                  "document.getElementById('received').textContent=this.value;}});"
                  "</script></body></html>")
            driver.get("data:text/html,"+quote(html))
            _enter_station(driver,"SS00085",lambda _msg:None)
            assert driver.find_element(By.ID,"received").text=="SS00085", "station/Enter test failed"
''')
print("v1.3 station automation patched")
