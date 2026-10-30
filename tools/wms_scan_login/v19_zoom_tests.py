import ctypes
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_zoom as z

class ChromeZoomFix(unittest.TestCase):
    def test_correct_win32_input_layout(self):
        self.assertEqual(ctypes.sizeof(z._KEYBDINPUT), 24 if ctypes.sizeof(ctypes.c_void_p)==8 else 16)
        self.assertEqual(ctypes.sizeof(z._INPUT), 40 if ctypes.sizeof(ctypes.c_void_p)==8 else 28)
        self.assertEqual(len(z._INPUT_UNION._fields_), 3)
    def test_actual_ctrl_minus_events(self):
        a=[z._keyboard_packet(z.VK_CONTROL),z._keyboard_packet(z.VK_OEM_MINUS),
           z._keyboard_packet(z.VK_OEM_MINUS,True),z._keyboard_packet(z.VK_CONTROL,True)]
        self.assertEqual([x.union.ki.dwFlags for x in a],[0,0,2,2])
        self.assertEqual([x.union.ki.wVk for x in a],[17,189,189,17])
    def test_only_maximize_not_restore(self):
        import inspect
        s=inspect.getsource(z._activate_verified_window)
        self.assertIn("ShowWindow(hwnd, SW_MAXIMIZE)",s)
        self.assertNotIn("ShowWindow(hwnd, SW_RESTORE)",s)
    def test_three_minus_after_reset(self):
        d=Mock()
        with patch.object(z,"_activate_verified_window",return_value=True), \
             patch.object(z,"_press_chrome_shortcut") as key, \
             patch.object(z,"_device_pixel_ratio",side_effect=[1.0,.75]), \
             patch.object(z.time,"sleep"):
            self.assertTrue(z._apply_zoom_steps(d,123,3,z.VK_OEM_MINUS))
        self.assertEqual([v.args[0] for v in key.call_args_list],[48,189,189,189])
if __name__=="__main__":
    unittest.main()
