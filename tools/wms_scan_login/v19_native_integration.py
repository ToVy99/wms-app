"""Integration check: real Chrome window native Ctrl+0 + Ctrl+- on Windows CI."""
import os
import sys
import tempfile
from pathlib import Path
from selenium import webdriver
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_zoom

def run():
    if os.name != "nt":
        return "SKIP: Windows required"
    with tempfile.TemporaryDirectory(prefix="wms_v19_zoom_") as tmp:
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--no-first-run")
        options.add_argument("--disable-notifications")
        options.add_argument(f"--user-data-dir={tmp}")
        driver = webdriver.Chrome(options=options)
        try:
            driver._wms_profile_path = tmp
            driver.get("data:text/html,<html><title>WMS Zoom Smoke</title><body><h1>BARCODE</h1></body></html>")
            before = float(driver.execute_script("return window.devicePixelRatio"))
            messages=[]
            success = native_zoom.native_chrome_zoom(driver,75,messages.append)
            after = float(driver.execute_script("return window.devicePixelRatio"))
            ratio = after / before
            return f'{"PASS" if success and abs(ratio-.75)<.045 else "FAIL"}: success={success}, pageDPRratio={ratio:.3f}, messages={messages}'
        finally:
            driver.quit()

if __name__=="__main__":
    try:
        result=run()
    except Exception as exc:
        result=f"FAIL: {type(exc).__name__}: {str(exc)[:300]}"
    print(result)
    Path("wms_native_zoom_smoke_result.txt").write_text(result+"\n",encoding="utf-8")
    sys.exit(1 if result.startswith("FAIL") else 0)
