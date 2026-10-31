"""v2.4 fast zoom regression tests."""
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import sys, inspect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import automation as a
import pack

class FastZoomTests(unittest.TestCase):
    def test_check_zooms_without_duplicate_wait_or_sleep(self):
        events=[]
        with patch.object(a,"_wait_station_applied",side_effect=lambda *_args,**kw:events.append("confirmed")), \
             patch.object(a,"_wait_work_page",side_effect=AssertionError("duplicate page wait")), \
             patch.object(a,"_set_browser_zoom",side_effect=lambda *_args,**kw:events.append("zoom") or True), \
             patch.object(a,"_focus_next_scanner",side_effect=lambda *_args,**kw:events.append("focus")):
            result=a._finalize_after_station(Mock(),"https://wms.ssc.shopee.vn/v2/salesoutbound/checkingnew",
                {"chrome_zoom_percent":75},station_code="SS00085",sleep=lambda *_:events.append("sleep"))
        self.assertTrue(result)
        self.assertEqual(events,["confirmed","zoom","focus"])
    def test_no_station_waits_for_ready_once(self):
        events=[]
        with patch.object(a,"_wait_station_applied",side_effect=AssertionError("no station")), \
             patch.object(a,"_wait_work_page",side_effect=lambda *_args,**kw:events.append("ready") or "station"), \
             patch.object(a,"_set_browser_zoom",side_effect=lambda *_args,**kw:events.append("zoom") or True), \
             patch.object(a,"_focus_next_scanner",side_effect=lambda *_args,**kw:events.append("focus")):
            a._finalize_after_station(Mock(),"https://wms.ssc.shopee.vn/v2/salesoutbound/checkingnew",
                {"chrome_zoom_percent":75},station_code="",sleep=lambda *_:events.append("sleep"))
        self.assertEqual(events,["ready","zoom","focus"])
    def test_pack_has_no_post_acknowledgement_sleep(self):
        source=inspect.getsource(pack.run_pack)
        tail=source[source.index("# The employee field has already been confirmed above."):]
        self.assertNotIn("sleep(1)",tail)
        self.assertNotIn("_wait_pack_ready(",tail)
    def test_station_ack_still_requires_stable_state(self):
        self.assertIn("stable_for=0.45",inspect.getsource(a._wait_station_applied))
if __name__=="__main__":unittest.main()
