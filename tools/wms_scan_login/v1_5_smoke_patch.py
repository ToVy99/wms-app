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

# Diagnose UI assertions clearly on Windows releases.
a = '''        assert app.settings_win.winfo_exists()
        assert app.zoom_selector.cget("state") == "readonly"
        assert "75%" in app.zoom_selector.cget("values")'''
b = '''        assert app.settings_win.winfo_exists(), "settings window missing"
        assert app.zoom_selector.winfo_exists(), "zoom selector missing"
        assert app.zoom_selector.cget("state") == "readonly", "zoom selector not readonly"
        assert "75%" in str(app.zoom_selector.cget("values")), "75% option missing"'''
s = p.read_text(encoding="utf-8")
assert s.count(a) == 1, "Missing zoom UI smoke section"
p.write_text(s.replace(a, b), encoding="utf-8")

# ttk Combobox option access differs across Windows Tcl versions.
s = p.read_text(encoding="utf-8")
a = '        self.zoom_selector.pack(side="right", ipady=5, padx=(10, 0))'
b = a + '\n        self.zoom_selector.state(["readonly"])'
assert s.count(a) == 1, "zoom widget placement missing"
s = s.replace(a, b)
a = '        assert app.zoom_selector.cget("state") == "readonly", "zoom selector not readonly"'
b = '        assert app.zoom_selector.instate(["readonly"]), "zoom selector not readonly"'
assert s.count(a) == 1, "readonly assertion missing"
p.write_text(s.replace(a, b), encoding="utf-8")
