"""Qt offscreen smoke test for the IntraCity 3.4 native Check Prod UI.

Tests require PySide6 and deliberately avoid WMS login or network requests.
Run: set QT_QPA_PLATFORM=offscreen && python -m unittest test_prod_native_layout
"""
import os
import unittest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QTabBar, QLabel, QPushButton
from productivity_tab import CheckProdTab, TABS


class FakeBridge(QObject):
    completed = Signal(str, str)
    sessionChanged = Signal(bool, str)
    connected = False
    session_message = 'Offline UI test'

    def request(self, *_args):
        raise AssertionError('UI layout smoke test must not call WMS')


class NativeProdLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.bridge = FakeBridge()
        self.widget = CheckProdTab(self.bridge, {}, lambda _config: True)
        self.widget.show()
        self.app.processEvents()

    def tearDown(self):
        self.widget.close()
        self.widget.deleteLater()
        self.app.processEvents()

    def test_all_work_tabs_remain_exposed(self):
        tabbar = self.widget.tab_select
        self.assertEqual([tabbar.tabText(i) for i in range(tabbar.count())], list(TABS))
        self.assertFalse(tabbar.usesScrollButtons())
        width = tabbar.sizeHint().width()
        for index in range(tabbar.count()):
            tabbar.setCurrentIndex(index)
            self.app.processEvents()
            self.assertEqual(tabbar.sizeHint().width(), width)

    def test_no_duplicate_connection_strip_above_controls(self):
        all_labels=[label.text() for label in self.widget.findChildren(QLabel)]
        self.assertFalse(any('Dữ liệu chung từ Chrome WMS' in text for text in all_labels))
        self.assertFalse(any('Chưa kết nối WMS' in text for text in all_labels))
        self.assertEqual(self.widget._wms_connected,False)
        self.bridge.sessionChanged.emit(True,'Đang dùng chung tab WMS')
        self.assertTrue(self.widget._wms_connected)
        self.assertEqual(self.widget._wms_connection_message,'Đang dùng chung tab WMS')

    def test_target_has_no_long_unit_label_and_all_modes_fixed(self):
        texts = [label.text() for label in self.widget.findChildren(QLabel)]
        self.assertNotIn('Items/h hoặc Orders/h', texts)
        buttons = (self.widget.bau,self.widget.cp,self.widget.item,self.widget.order,
                   self.widget.shift1,self.widget.shift2)
        for btn in buttons:
            self.assertEqual(btn.width(),72)
            self.assertEqual(btn.height(),34)

    def test_dark_light_styling_and_metric_icons(self):
        icons=[label for label in self.widget.findChildren(QLabel) if label.objectName()=='prodMetricIcon']
        self.assertEqual(len(icons), 5)
        for light in (True,False,True):
            self.widget.set_theme(light)
            self.assertEqual(self.widget._light_theme,light)
            self.assertIn('QFrame#prodMetricCard',self.widget.styleSheet())
            self.assertIn('QPushButton[prodChoice="true"]:checked', self.widget.styleSheet())
        self.assertEqual(set(self.widget.metric_values),{'qty','weighted','avg','manHour','below'})
        self.assertFalse(self.bridge.connected)


if __name__ == '__main__':
    unittest.main()
