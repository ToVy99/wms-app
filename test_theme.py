"""Appearance changes must preserve loaded orders, selection and API inactivity."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
import intra_2_3_COT_Dashboard_loginfix as intra
CHECK_FOR_UPDATES=intra.WMSDashboard.check_for_updates

class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.saved=[]
        self.patches=[patch.object(intra,'load_config',return_value={'appearance':'dark','seen_release':'3.4','seen_release_id':'3.4-compact-bridge-20261017'}),patch.object(intra,'save_config',side_effect=lambda c:self.saved.append(dict(c)) or True),patch.object(intra.WMSDashboard,'start_folder_watcher'),patch.object(intra.WMSDashboard,'check_for_updates')]
        for p in self.patches:p.start()
        self.window=intra.WMSDashboard()
        self.tab=self.window.cotTab
        self.calls=[];self.tab.request=lambda m,c:self.calls.append(m)
    def tearDown(self):
        self.window.theme_controller.disconnect_signals()
        self.window.close()
        for p in reversed(self.patches):p.stop()
    def choose(self,mode):self.window.themeChoice.setCurrentIndex(self.window.themeChoice.findData(mode))
    def test_switch_preserves_orders_filters_and_checked_buttons(self):
        self.tab.orders=[dict(order_number='OB1',order_status=3,sns={'SN1'},picking={'P1'},bsks={'BSK1'},area='A1',wave_type='Single',sku_names={'Áo'},ctime_text='',cutoff_text='')]
        self.tab.active_status=3;self.tab.render_all();self.tab.search.setText('OB1');self.tab.select_visible()
        metric=self.tab.total_card.styleSheet()
        for mode in ['light','dark','light','dark']:
            self.choose(mode)
            self.assertEqual(self.tab.table.rowCount(),1);self.assertEqual(self.tab.selected,{'OB1'})
            self.assertEqual(self.tab.search.text(),'OB1');self.assertTrue(self.tab.status_buttons[3].isChecked())
            self.assertEqual(self.tab.total_card.styleSheet(),metric)
        self.assertEqual(self.calls,[]);self.assertIsNone(self.tab.bridge.worker)
        self.assertEqual(self.saved[-1]['appearance'],'dark')
    def test_system_tracks_changes_only_in_system_mode(self):
        controller=self.window.theme_controller;self.choose('system')
        controller.system_changed(Qt.ColorScheme.Light);self.assertTrue(controller.light)
        controller.system_changed(Qt.ColorScheme.Dark);self.assertFalse(controller.light)
        self.choose('light');controller.system_changed(Qt.ColorScheme.Dark);self.assertTrue(controller.light)
        self.choose('dark');controller.system_changed(Qt.ColorScheme.Light);self.assertFalse(controller.light)
        self.assertEqual(self.calls,[])
    def test_light_survives_dynamic_cot_and_banner_updates(self):
        self.choose('light');self.tab.carrier.setCurrentIndex(1)
        self.assertIn('#fff0c2',self.tab.cot_buttons[0][1].styleSheet())
        self.window.set_banner_status(False,True,'Đã tải')
        self.assertIn('#dcfce7',self.window.statusBanner.styleSheet())
        self.choose('dark');self.assertIn('#2e3c38',self.window.statusBanner.styleSheet())
        self.assertEqual(self.window.windowTitle(),'IntraCity 3.4')
        self.assertEqual(self.calls,[])

    def test_update_notice_once_per_version_while_app_remains_open(self):
        with patch.object(intra.QMessageBox,'question',return_value=intra.QMessageBox.No) as question:
            self.window.prompt_update({'version':'3.4','download_url':'https://example.com/app.exe'})
            self.window.prompt_update({'version':'3.4'})
            self.window.prompt_update({'version':'3.5'})
            self.assertEqual(question.call_count,2)
        self.assertTrue(self.window.update_timer.isActive())
        self.assertEqual(self.window.update_timer.interval(),600000)
        self.assertEqual(self.calls,[])

    def test_periodic_update_skips_running_check_and_stops_on_close(self):
        from unittest.mock import MagicMock
        worker=MagicMock();worker.isRunning.return_value=True
        self.window.updater_thread=worker
        with patch.object(intra,'AutoUpdaterThread') as factory:
            CHECK_FOR_UPDATES(self.window);factory.assert_not_called()
            worker.isRunning.return_value=False
            CHECK_FOR_UPDATES(self.window);factory.return_value.start.assert_called_once()
            worker.deleteLater.assert_called_once()
        self.window.updater_thread=None
        self.window.close();self.assertFalse(self.window.update_timer.isActive())
        self.assertEqual(self.calls,[])

    def test_filter_popups_open_on_first_click_and_after_theme_switch(self):
        from PySide6.QtTest import QTest
        self.window.mainTabs.setCurrentIndex(1);self.window.show()
        self.window.combo3PL.populate_items(['SPX Express','Ahamove'],['SPX Express'])
        self.window.comboState.populate_items(['Hà Nội','Bắc Ninh'],['Hà Nội'])
        for mode in ['dark','light','dark']:
            self.choose(mode)
            for combo in [self.window.combo3PL,self.window.comboState]:
                QTest.mouseClick(combo.lineEdit(),Qt.LeftButton)
                QTest.qWait(20)
                self.assertTrue(combo.view().isVisible())
                self.assertEqual(combo.model().rowCount(),3)
                self.assertEqual(len(combo.get_checked_items()),1)
                self.assertIn('background:#ffffff' if mode=='light' else 'background:#181825',combo.view().styleSheet())
                combo.hidePopup()
        self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()
