"""Portable IntraCity 3.4 UI guardrails; safe without Qt/Chrome/real WMS."""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parent

class NativeUIStaticTests(unittest.TestCase):
    def test_main_tabs_have_their_own_unclipped_row(self):
        text=(ROOT/'intra_2_3_COT_Dashboard_loginfix.py').read_text(encoding='utf-8')
        self.assertIn('root.insertLayout(1,navigation)',text)
        self.assertIn('self.topTabs.setUsesScrollButtons(False)',text)
        self.assertIn('self.topTabs.setSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed)',text)
        self.assertNotIn('global_top.addWidget(self.topTabs,0,Qt.AlignCenter)',text)
        self.assertNotIn("self.btnCheckProd=QPushButton(",text)
        self.assertEqual(text.count("self.topTabs.addTab('📈 Check Prod')"),1)
        self.assertIn("self.topTabs.addTab('📊 Excel / Outbound')",text)
        self.assertNotIn("self.topTabs.addTab('📊 Check Prod')",text)
        self.assertIn("self.mainTabs.insertTab(2,self.check_prod_tab,'📈 Check Prod')",text)

    def test_checkprod_has_stable_work_tabs_and_separate_target_row(self):
        text=(ROOT/'productivity_tab.py').read_text(encoding='utf-8')
        self.assertIn('self.tab_select.setUsesScrollButtons(False)',text)
        self.assertIn("self.tab_select.setObjectName('prodWorkTabs')",text)
        self.assertIn('target_row=QHBoxLayout();main.addLayout(target_row)',text)
        self.assertIn('work_row=QHBoxLayout();main.addLayout(work_row)',text)
        self.assertNotIn("tools.addWidget(QLabel('Items/h hoặc Orders/h'))",text)
        self.assertIn('button.setFixedSize(72,34)',text)
        self.assertIn("QPushButton[prodChoice=\"true\"]:checked",text)
        self.assertIn('symbol.setFixedSize(50,50)',text)
        self.assertNotIn("statusbar=QHBoxLayout();main.addLayout(statusbar)",text)
        self.assertNotIn('Dữ liệu chung từ Chrome WMS',text)
        self.assertIn('self._wms_connected=bool(connected)',text)

    def test_no_business_calculation_or_wms_bridge_edits(self):
        # These modules should remain outside the visual-layout changeset.
        text=(ROOT/'productivity_tab.py').read_text(encoding='utf-8')
        tree=ast.parse(text)
        self.assertTrue(any(isinstance(n,ast.ClassDef) and n.name=='CheckProdTab' for n in tree.body))
        self.assertNotIn('QWebEngineView',text)
        self.assertEqual((ROOT/'release_notes.py').read_text(encoding='utf-8').count("VERSION='3.4'"),1)

if __name__ == '__main__':unittest.main()
