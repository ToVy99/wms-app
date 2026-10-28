"""Static checks for the three-tab IntraCity 3.4 layout."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parent
class LeanUIStaticTests(unittest.TestCase):
    def test_sku_embedded_not_separate_button(self):
        code=(ROOT/'intra_2_3_COT_Dashboard_loginfix.py').read_text(encoding='utf-8')
        for expected in ("self.topTabs.addTab('⚡ COT')","self.topTabs.addTab('📊 Excel / Outbound')",
                         "self.topTabs.addTab('🔍 Tìm SKU')",
                         "self.mainTabs.addTab(self.sku_tab, '🔍 Tìm SKU')",
                         "embedded=True","root.insertLayout(1,navigation)"):
            self.assertIn(expected,code)
        self.assertNotIn('self.btnSkuTask',code)
        self.assertNotIn('Check Prod',code)
    def test_productivity_removed_persistent_chrome(self):
        chrome=(ROOT/'chrome_cot.py').read_text(encoding='utf-8')
        self.assertIn('launch_persistent_context(',chrome)
        self.assertIn("chrome_profile_dir()",chrome)
        self.assertNotIn("data_wms__warehouse_operation_whs__outbound_productivity_info_ri",chrome)
        self.assertFalse((ROOT/'productivity_tab.py').exists())
        self.assertFalse((ROOT/'prod_native_core.py').exists())
        self.assertIn("VERSION='3.4'",(ROOT/'release_notes.py').read_text(encoding='utf-8'))
if __name__=='__main__':unittest.main()
