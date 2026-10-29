"""Patch v1.2 for WMS Scan Login. Applied during the Windows build."""
from pathlib import Path

root = Path(__file__).resolve().parents[2] / "scan_build"
assert (root / "automation.py").is_file(), root
assert (root / "main.py").is_file(), root

def replace_once(path, before, after):
    contents = path.read_text(encoding="utf-8")
    assert contents.count(before) == 1, f"{path}: expected 1 occurrence; got {contents.count(before)} for {before!r}"
    path.write_text(contents.replace(before, after), encoding="utf-8")

auto = root / "automation.py"
replace_once(
    auto,
    'AUTH_HOST = "wfm.business.accounts.shopee.com"',
    'AUTH_HOSTS = {"wfm.business.accounts.shopee.com", "wms.business.accounts.shopee.com"}'
)
replace_once(
    auto,
    "if host == AUTH_HOST or _auth_visible(driver, cfg):",
    "if host in AUTH_HOSTS or _auth_visible(driver, cfg):"
)
replace_once(
    auto,
    'status(f"{lane}: Mở trang WMS và chờ chuyển tới Shopee WFM...")',
    'status(f"{lane}: Đang mở WMS và trang đăng nhập Shopee Accounts...")'
)
replace_once(
    auto,
    '"Không thấy ô User ID/Password trên trang đăng nhập WFM sau 50 giây. "',
    '"Không thấy ô User ID/Password trên trang Shopee Accounts sau 50 giây. "'
)
replace_once(
    auto,
    '"Không nhận diện được User ID hoặc Password trên WFM."',
    '"Không nhận diện được User ID hoặc Password trên trang Shopee Accounts."'
)

main = root / "main.py"
replace_once(
    main,
    'import os\nimport traceback',
    'import os\nimport sys\nfrom pathlib import Path\nimport traceback'
)
replace_once(
    main,
    '        from automation import AutomationError, SessionManager\n        manager = SessionManager()',
    '''        try:
            from automation import AutomationError, SessionManager
            manager = SessionManager()
        except ModuleNotFoundError as exc:
            name = exc.name or "khong ro"
            self.messages.put(f"LỖI: Thiếu module {name}. Cần EXE build với đủ thư viện.")
            return
        except Exception as exc:
            self.messages.put(f"LỖI khởi tạo: {type(exc).__name__}.")
            return'''
)
replace_once(
    main,
    '                    # Never write credentials, error strings or browser page HTML.\n',
    '''                    # Only write the missing module's NAME, never credentials or browser contents.
                    module_detail = ("Missing module: " + (exc.name or "unknown")) if isinstance(exc, ModuleNotFoundError) else ""
'''
)
replace_once(
    main,
    '                        log.write(f"\\n[{datetime.now():%Y-%m-%d %H:%M:%S}] {lane}\\n{detail}\\n")',
    '                        log.write(f"\\n[{datetime.now():%Y-%m-%d %H:%M:%S}] {lane} {type(exc).__name__} {module_detail}\\n{detail}\\n")'
)
replace_once(
    main,
    '                self.messages.put(f"LỖI: {type(exc).__name__}. Xem %LOCALAPPDATA%\\\\WMS_Scan_Login\\\\errors.log")',
    '''                module_hint = f" - thiếu {exc.name}" if isinstance(exc, ModuleNotFoundError) else ""
                self.messages.put(f"LỖI: {type(exc).__name__}{module_hint}. Xem %LOCALAPPDATA%\\\\WMS_Scan_Login\\\\errors.log")'''
)
selftest = '''
def _self_test():
    """Exercise Chrome and Selenium inside the actual frozen Windows EXE."""
    import tempfile
    from pathlib import Path
    result = Path.cwd() / "wms_scan_smoke_result.txt"
    driver = None
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from automation import SessionManager, _host
        assert _host("https://wms.business.accounts.shopee.com/authenticate/login") == "wms.business.accounts.shopee.com"
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-first-run")
        with tempfile.TemporaryDirectory(prefix="wms_smoke_") as folder:
            options.add_argument(f"--user-data-dir={folder}")
            driver = webdriver.Chrome(options=options)
            driver.get("data:text/html,<html><head><title>WMS smoke test</title></head><body>OK</body></html>")
            assert driver.title == "WMS smoke test"
            driver.quit()
            driver = None
        result.write_text("PASS: Frozen Selenium imported and Chrome launched.\\\\n", encoding="utf-8")
        return 0
    except Exception as exc:
        result.write_text(f"FAIL: {type(exc).__name__}: {str(exc)[:400]}\\\\n", encoding="utf-8")
        return 1
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

'''
replace_once(
    main,
    'if __name__ == "__main__":\n    main()',
    selftest + 'if __name__ == "__main__":\n    if "--self-test" in sys.argv:\n        sys.exit(_self_test())\n    main()'
)

tests = root / "tests" / "test_auth_domains.py"
tests.write_text('''import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automation import AUTH_HOSTS, _host, _explain_login_failure

class TestAuthDomains(unittest.TestCase):
    def test_both_hosts_supported(self):
        self.assertIn("wfm.business.accounts.shopee.com", AUTH_HOSTS)
        self.assertIn("wms.business.accounts.shopee.com", AUTH_HOSTS)
    def test_host_from_user_redirect(self):
        url = ("https://wms.business.accounts.shopee.com/authenticate/login?"
               "lang=en&client_id=19&next=https%3A%2F%2Fwms.ssc.shopee.vn%2Fv2%2Ftob%2Fcallback")
        self.assertIn(_host(url), AUTH_HOSTS)

if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")

print("Patched Selenium login host, missing-module diagnostics and frozen smoke test.")
