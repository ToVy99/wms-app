"""Regression guard for IntraCity 3.4 Area button-only presentation and approved release notes."""
import ast
import re
import unittest
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent

class AreaReleaseUIRegression(unittest.TestCase):
    def test_area_buttons_share_one_horizontal_row(self):
        text = (ROOT / 'chrome_cot.py').read_text(encoding='utf-8')
        tree = ast.parse(text)
        self.assertNotIn('self.area_summary', text)
        self.assertIn('self.area_buttons_layout=QHBoxLayout(self.area_buttons_host)', text)
        self.assertIn('choices=[(None, f\'Tất cả · {total}\')]', text)
        self.assertIn('self.area_buttons_layout.addWidget(button)', text)
        self.assertIn('self.area_buttons_layout.addStretch(1)',text)
        self.assertIn('self.update_area_buttons(area_counts, len(src))', text)
        self.assertIn('self.active_area=None if area==self.active_area else area', text)
        self.assertIn('src=self.status_orders()', text)
        self.assertIn('self.area_buttons_scroll.setFixedHeight(38)', text)
        self.assertTrue(any(isinstance(n,ast.ClassDef) and n.name=='ChromeCotTab' for n in tree.body))

    def test_release_note_is_approved_copy_and_version_34(self):
        notes=(ROOT/'release_notes.py').read_text(encoding='utf-8')
        self.assertIn("VERSION='3.4'", notes)
        self.assertIn('Đỗ Rê Mon♥!', notes)
        self.assertIn('Giảm chiều cao các ô.', notes)
        self.assertIn('Một phiên Chrome/WMS:', notes)
        self.assertIn('Lọc Area bằng nút:', notes)
        self.assertIn('Kết hợp tool tìm mã rổ', notes)
        self.assertNotIn('Việt hóa giao diện:', notes)
        self.assertNotIn('Đảo thứ tự Prod:', notes)
        self.assertNotIn('Giao diện gốc IntraCity:', notes)
        self.assertNotIn('3.5', notes)

if __name__=='__main__': unittest.main()
