import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import io,zipfile,tempfile,unittest,base64
from pathlib import Path
from unittest.mock import patch
from contextlib import nullcontext
from openpyxl import Workbook
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from cot_logic import parse_report,progress
from cot_widgets import SlidingOrders
from test_native_cot import fixture
from chrome_cot import ChromeCotTab
import intra_2_3_COT_Dashboard_loginfix as intra
from release_notes import VERSION,show_changes
HEAD=['WMS Order No','Status','New 3PL','Buyer State','SKU Name','Picking ID','Basket ID']
def workbook(sheets):
    wb=Workbook();wb.remove(wb.active)
    for name,rows in sheets:
        ws=wb.create_sheet(name)
        for row in rows:ws.append(row)
    out=io.BytesIO();wb.save(out);return out.getvalue()
def zipped(parts):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in parts:z.writestr(name,data)
    return out.getvalue()
class Release33Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_split_report_equals_single_report_both_readers(self):
        a=['A','Picked','SPX Express SBS - Trong Ngày','Bắc Ninh','SKU1','P1','B1']
        b=['A','Picked','SPX Express SBS - Trong Ngày','Bắc Ninh','SKU2','P2','B2']
        c=['B','Outbound','SPX Express SBS - Trong Ngày','Bắc Ninh','SKU3','P3','B3']
        cancel=['C','Cancel','SPX Express SBS - Trong Ngày','Bắc Ninh'];wrong=['W','Picked','Ahamove','Hà Nội']
        data=zipped([('part1.xlsx',workbook([('Orders',[HEAD,wrong])])),('folder/PART2.XLSX',workbook([('Notes',[['Export report']]),('Orders',[HEAD,a,cancel]),('More',[HEAD,b,c])])),('readme.txt',b'Export'),('__MACOSX/._part1.xlsx',b'ignore')])
        expected=parse_report(workbook([('Orders',[HEAD,wrong,a,cancel,b,c])]),'one.xlsx','sdd')
        for fallback in [False,True]:
            with patch('pandas.ExcelFile',side_effect=RuntimeError()) if fallback else nullcontext():
                result=parse_report(data,'report.zip','sdd')
            self.assertEqual(result['orders'],expected['orders']);self.assertEqual(result['rawRows'],5)
            self.assertEqual((result['reportFiles'],result['reportSheets']),(2,3));self.assertEqual(progress(result['orders']),(1,2,50.0))
            self.assertEqual(result['orders'][0]['sku_names'],{'SKU1','SKU2'});self.assertEqual(result['orders'][0]['picking'],{'P1','P2'});self.assertEqual(result['orders'][0]['bsks'],{'B1','B2'})
    def test_bad_part_fails_without_partial_result(self):
        valid=fixture([['A','Picked','SPX Express','Hà Nội']])
        for broken in [b'broken',workbook([('Sheet',[['WMS Order No'],['B']])])]:
            with self.assertRaisesRegex(ValueError,'bad.xlsx'):parse_report(zipped([('good.xlsx',valid),('bad.xlsx',broken)]),'all.zip','intra')
    def test_cells_column_copy_and_picked_baskets(self):
        tab=ChromeCotTab({},lambda c:True);tab.resize(1280,720);tab.show()
        try:
            tab.orders=parse_report(fixture([['A','Picked','SPX Express','Hà Nội','SN1','Single','P1','','B1'],['B','Outbound','SPX Express','Hà Nội','SN2','Single','P2','','B2']]),'x.xlsx','intra')['orders'];tab.render_all()
            calls=[];tab.request=lambda *args:calls.append(args)
            self.assertEqual(tab.table.item(0,4).text(),'B1');self.assertEqual(tab.table.item(1,4).text(),'');self.assertEqual(tab.basket_filter.text(),'Picked có mã rổ')
            self.app.processEvents();QTest.mouseClick(tab.table.viewport(),Qt.LeftButton,pos=tab.table.visualItemRect(tab.table.item(0,1)).center())
            self.assertEqual([(i.row(),i.column()) for i in tab.table.selectedIndexes()],[(0,1)])
            QTest.keyClick(tab.table,Qt.Key_C,Qt.ControlModifier);self.assertEqual(self.app.clipboard().text(),'A')
            tab.table.scrollToItem(tab.table.item(0,9));self.app.processEvents();header=tab.table.horizontalHeader()
            QTest.mouseClick(header.viewport(),Qt.LeftButton,pos=QPoint(header.sectionViewportPosition(9)+10,header.height()//2))
            self.assertEqual({i.column() for i in tab.table.selectedIndexes()},{9});tab.table.copy_selection();self.assertEqual(self.app.clipboard().text(),'P1\nP2')
            self.assertIn('#ffd45c',tab.table.styleSheet());self.assertEqual(calls,[])
        finally:tab.close();tab.deleteLater()
    def test_overlay_keeps_upper_fixed_and_restores_position(self):
        saved=[];config={};panel=SlidingOrders(config,lambda c:saved.append(dict(c)) or True);panel.resize(1200,650);panel.show();self.app.processEvents()
        original=panel.upper.geometry();oldheight=panel.lower.height();panel.handle.moved.emit(-100);self.app.processEvents()
        self.assertEqual(panel.upper.geometry(),original);self.assertEqual(panel.lower.y(),128);self.assertGreater(panel.lower.height(),oldheight)
        panel.handle.released.emit();self.assertEqual(saved[-1]['cot_panel_reveal'],128)
        panel.toggle();self.assertEqual(panel.lower.y(),0);panel.toggle();self.assertEqual(panel.lower.y(),128)
        restored=SlidingOrders(config,lambda c:True);self.assertEqual(restored.reveal,128)
        panel.close();restored.close();panel.deleteLater();restored.deleteLater()
    def test_save_original_bytes_without_requests(self):
        tab=ChromeCotTab({},lambda c:True);self.assertFalse(tab.save_report.isEnabled())
        raw=zipped([('a.xlsx',fixture([])),('b.xlsx',fixture([]))]);tab.scope=tab.current_range();tab.report_name='report.xlsx'
        try:
            tab.got_bytes(base64.b64encode(raw).decode());tab.parser.wait(10000);self.app.processEvents();calls=[];tab.request=lambda *args:calls.append(args);tab.select_cot('2')
            self.assertTrue(tab.save_report.isEnabled())
            with tempfile.TemporaryDirectory() as td,patch('chrome_cot.QFileDialog.getSaveFileName',return_value=(td+'/report.zip','')) as pick:
                tab.save_original_report();self.assertEqual(Path(td+'/report.zip').read_bytes(),raw);self.assertTrue(pick.call_args.args[2].endswith('.zip'))
            self.assertEqual(calls,[])
        finally:tab.close();tab.deleteLater()
    def test_whats_new_ack_once_and_reopen(self):
        with patch.object(intra,'load_config',return_value={'seen_release':VERSION}),patch.object(intra.WMSDashboard,'start_folder_watcher'),patch.object(intra.WMSDashboard,'check_for_updates'):
            window=intra.WMSDashboard();self.app.processEvents()
        try:
            window.config.pop('seen_release',None);saved=[];show_changes(window,lambda c:saved.append(dict(c)) or True,automatic=True)
            self.assertTrue(window._whats_new_dialog.isVisible());window._whats_new_dialog.accept();self.app.processEvents();self.assertEqual(saved[-1]['seen_release'],VERSION)
            show_changes(window,lambda c:True,automatic=True);self.assertIsNone(window._whats_new_dialog)
            show_changes(window,lambda c:True);self.assertTrue(window._whats_new_dialog.isVisible());window._whats_new_dialog.reject()
            window.config.pop('seen_release',None)
            with patch('release_notes.QMessageBox.warning'):
                show_changes(window,lambda c:False);window._whats_new_dialog.accept()
            self.assertNotIn('seen_release',window.config)
        finally:window.close();window.theme_controller.disconnect_signals();window.deleteLater()
if __name__=='__main__':unittest.main()
