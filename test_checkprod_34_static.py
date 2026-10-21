"""Off-line regression tests: no live WMS/API calls or Qt instance required."""
import ast
import copy
import hashlib
import os
from pathlib import Path
import re
import textwrap
import unittest

HERE=Path(__file__).resolve().parent


class CheckProdStaticTests(unittest.TestCase):
    def test_version_and_original_formula_files(self):
        notes=(HERE/'release_notes.py').read_text(encoding='utf-8')
        self.assertIn("VERSION='3.4'",notes)
        self.assertIn('Check Prod',notes)
        self.assertIn('Lọc Area',notes)
        self.assertTrue((HERE/'productivity/core.js').exists())
        self.assertTrue((HERE/'productivity/api.js').exists())

    def test_browser_transport_whitelists_approved_endpoints(self):
        path='/mgmt/api/wms_pc/forward_wms_be/api/v2/openapi/mgmt/workspace/pc/data_wms__warehouse_operation_whs__outbound_productivity_info_ri'
        native=(HERE/'chrome_cot.py').read_text(encoding='utf-8')
        extension=(HERE/'wms_bridge_content.js').read_text(encoding='utf-8')
        for route in (path, '/api/v2/apps/process/taskcenter/checkingtask/search_checking_task',
                      '/api/v2/apps/process/taskcenter/sortingtask/search_sorting_task',
                      '/api/v2/apps/process/outbound/packing/search_packing_task'):
            self.assertIn(route,native)
            self.assertIn(route,extension)
        self.assertIn('wms.ssc.shopee.vn',native)

    def test_area_and_status_intersection(self):
        src=(HERE/'chrome_cot.py').read_text(encoding='utf-8')
        tree=ast.parse(src)
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ChromeCotTab')
        methods=['status_orders','visible','area_groups','search_text','order_search_text','select_status','choose_area']
        selected=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in methods]
        # Execute actual source methods without importing Qt; stub rendering/network.
        namespace={'re':re, 'unicodedata':__import__('unicodedata'), 'status_name':lambda x:str(x)}
        shell='class Stub:\n'+textwrap.indent('\n\n'.join(ast.unparse(n) for n in selected),'    ')
        exec(shell,namespace)
        x=namespace['Stub']()
        x.orders=[{'order_status':3,'area':'A1','wave_type':'One','order_number':'1','sns':{'S1'}},
                  {'order_status':3,'area':'B2','wave_type':'One','order_number':'2','sns':{'S2'}},
                  {'order_status':6,'area':'A3','wave_type':'One','order_number':'3','sns':{'S3'}}]
        x.active_status=3;x.active_area='A';x.active_wave=None;x.picked_baskets_only=False
        x.selected=set();x.busy=False;x.area_loaded={'3','6'}
        x.search=type('Search',(),{'text':lambda self:''})()
        x.basket_codes=lambda _:[];x.render_all=lambda:None
        self.assertEqual([o['order_number'] for o in x.visible()],['1'])
        before=copy.deepcopy(x.orders)
        x.select_status(6)
        self.assertEqual(x.active_area,'A')
        self.assertEqual([o['order_number'] for o in x.visible()],['3'])
        x.select_status(3)
        x.choose_area('A')
        self.assertIsNone(x.active_area)
        self.assertEqual({o['order_number'] for o in x.visible()},{'1','2'})
        self.assertEqual(x.orders,before)
        self.assertEqual(x.area_groups({'area':'C1,B2,LC4,CF1'}),{'C','B','LC','CF'})

    def test_sort_direction_is_display_only(self):
        source=(HERE/'productivity/popup.js').read_text(encoding='utf-8')
        self.assertIn('prodAscending ? x-y : y-x',source)
        self.assertIn('sortForView(list, tab)',source)
        self.assertIn('Cao → Thấp',source)
        self.assertIn('Thấp → Cao',source)
        self.assertIn('window.__prodExport(headers, rows)',source)

    def test_main_app_launches_prod_only_when_clicked(self):
        src=(HERE/'intra_2_3_COT_Dashboard_loginfix.py').read_text(encoding='utf-8')
        self.assertIn("self.topTabs.addTab('📊 Check Prod')",src)
        self.assertNotIn('self.btnCheckProd=QPushButton(',src)
        self.assertIn('self.topTabs.currentChanged.connect(self._on_top_tab_changed)',src)
        self.assertIn('from productivity_tab import CheckProdTab',src)
        self.assertIn('self.cotTab.bridge,self.config,save_config,self',src)
        self.assertIn('self.check_prod_tab=None',src)
        self.assertNotIn('QWebEngineView',(HERE/'productivity_tab.py').read_text(encoding='utf-8'))
        build=(HERE/'build_windows.ps1').read_text(encoding='utf-8')
        self.assertIn('--exclude-module PySide6.QtWebEngineWidgets', build)
        self.assertNotIn('--hidden-import PySide6.QtWebEngineWidgets', build)

if __name__=='__main__':unittest.main()
