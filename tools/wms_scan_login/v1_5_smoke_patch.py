"""Keep frozen Chrome zoom smoke test correct on Windows 125%/150% display scaling."""
from pathlib import Path
p = Path("scan_build/main.py")
s = p.read_text(encoding="utf-8")
a = """            assert _set_browser_zoom(driver, 75, lambda _status: None)
            css_zoom = driver.execute_script("return document.documentElement.style.zoom")
            chrome_dpr = float(driver.execute_script("return window.devicePixelRatio") or 1)
            assert css_zoom in ("75%", "0.75") or chrome_dpr < 0.85, (css_zoom, chrome_dpr)"""
b = """            baseline_dpr = float(driver.execute_script("return window.devicePixelRatio") or 1)
            assert _set_browser_zoom(driver, 75, lambda _status: None)
            css_zoom = driver.execute_script("return document.documentElement.style.zoom")
            chrome_dpr = float(driver.execute_script("return window.devicePixelRatio") or 1)
            assert css_zoom in ("75%", "0.75") or abs(chrome_dpr / baseline_dpr - 0.75) < 0.055, (css_zoom, chrome_dpr, baseline_dpr)"""
assert s.count(a) == 1, "v1.5 zoom smoke-test patch target missing"
p.write_text(s.replace(a,b), encoding="utf-8")
