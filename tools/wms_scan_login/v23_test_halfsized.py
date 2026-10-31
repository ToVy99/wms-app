"""Regressions for the v2.3 compact mini and one-second after-station delay."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main

class HalfSizedTests(unittest.TestCase):
    def test_mini_dimensions_are_small(self):
        self.assertGreaterEqual(main.MINI_WIDTH, 360)
        self.assertLessEqual(main.MINI_WIDTH, 400)
        self.assertLessEqual(main.MINI_HEIGHT, 130)

    def test_minibar_shows_both_lanes_and_stop(self):
        import tkinter as tk
        if os.name == 'nt' or os.environ.get('DISPLAY'):
            from unittest.mock import patch
            with patch.object(main, 'read_config', return_value={
                'keep_on_top': False, 'start_mini':True, 'encrypted_password':'test',
                'dock_bottom_left':False,'remember_window_position':False}):
                root=tk.Tk()
                try:
                    app=main.WMSScanApp(root)
                    root.update()
                    self.assertEqual((root.winfo_width(), root.winfo_height()),
                                     (main.MINI_WIDTH,main.MINI_HEIGHT))
                    self.assertTrue(app.mini_stop.winfo_ismapped())
                    self.assertTrue(app.mini_pause.winfo_ismapped())
                    self.assertTrue(app.mini_login.winfo_ismapped())
                    self.assertTrue(app.mini_entries['CHECK'].winfo_ismapped())
                    self.assertFalse(app.mini_entries['PACK'].winfo_ismapped())
                    app._switch_lane('PACK')
                    root.update()
                    self.assertTrue(app.mini_entries['PACK'].winfo_ismapped())
                    self.assertFalse(app.mini_entries['CHECK'].winfo_ismapped())
                    app.status.set('Test '*200)
                    self.assertLessEqual(len(app.mini_status_var.get()),54)
                finally:
                    root.destroy()
        else:
            self.skipTest('Display required')

    def test_check_waits_one_second_only_after_ready(self):
        try:
            import automation as a
        except ImportError:
            self.skipTest('Selenium unavailable')
        events=[]
        with (patch.object(a,'_wait_station_applied', side_effect=lambda *_args,**_kw:events.append('ready')),
              patch.object(a,'_wait_work_page', side_effect=lambda *_args,**_kw:events.append('recheck')),
              patch.object(a,'_set_browser_zoom', side_effect=lambda *_args,**_kw:events.append('zoom') or True),
              patch.object(a,'_focus_next_scanner', side_effect=lambda *_args,**_kw:events.append('focus'))):
            self.assertTrue(a._finalize_after_station(Mock(), 'https://wms.ssc.shopee.vn/v2/salesoutbound/checkingnew',
                {'chrome_zoom_percent':75},station_code='SS00085',sleep=lambda n:events.append(('sleep',n))))
        self.assertEqual(events,['ready',('sleep',1),'recheck','ready','zoom','focus'])

if __name__=='__main__':
    unittest.main()