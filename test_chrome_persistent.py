"""Offline tests: persistent Chrome WMS profile stays on the user's Windows machine."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from chrome_cot import chrome_profile_dir, ChromeWorker, validate_request

class ChromeProfileTests(unittest.TestCase):
    def test_profile_uses_local_app_data(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.dict(os.environ,{'LOCALAPPDATA':d}):
                self.assertEqual(chrome_profile_dir(),Path(d)/'IntraCity'/'ChromeProfile')
    def test_wms_cot_and_sku_allowed_but_old_prod_disallowed(self):
        validate_request({'type':'WMS_POST','url':'https://wms.ssc.shopee.vn/api/v2/apps/process/outbound/salesorder/search_order','body':{}})
        with self.assertRaises(ValueError):
            validate_request({'type':'WMS_POST','url':'https://wms.ssc.shopee.vn/api/v2/apps/process/outbound/packing/search_packing_task','body':{}})
    def test_no_browser_or_request_at_startup(self):
        worker=ChromeWorker()
        self.assertEqual(worker.network_requests,0)
        self.assertFalse(worker.isRunning())
        worker.deleteLater()
if __name__=='__main__':unittest.main()
