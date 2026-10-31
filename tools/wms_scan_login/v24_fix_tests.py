"""v2.4: remove historical test hunks from diff, then update old test expectations."""
from pathlib import Path
import sys

def replace_once(path, old, new):
    content=path.read_text(encoding="utf-8")
    if content.count(old)!=1:
        raise RuntimeError(f"Expected one marker in {path}: {old[:70]}; got {content.count(old)}")
    path.write_text(content.replace(old,new),encoding="utf-8")

def strip_patch():
    p=Path("v24_patch.diff")
    s=p.read_text(encoding="utf-8")
    pos=s.index("--- a/scan_build/tests/")
    p.write_text(s[:pos],encoding="utf-8")
    print("Kept application logic patch only",pos,"characters")

def update_tests():
    root=Path("scan_build/tests")
    replace_once(root/"test_v23_halfsized.py","test_check_waits_one_second_only_after_ready",
                 "test_check_zooms_immediately_after_confirmation")
    replace_once(root/"test_v23_halfsized.py",
                 "['ready',('sleep',1),'recheck','ready','zoom','focus']",
                 "['ready','zoom','focus']")
    replace_once(root/"test_v17_browser.py","[('sleep',1),'zoom']","['zoom']")
    replace_once(root/"test_v17_sequence.py",
                 "['confirmed',('sleep',1),'still-ready','confirmed','zoom','focus']",
                 "['confirmed','zoom','focus']")
    replace_once(root/"test_v18_virtual_zoom.py",
                 "['confirmed', ('sleep', 1), 'ready', 'confirmed', 'zoom', 'focus']",
                 "['confirmed','zoom','focus']")
    replace_once(root/"test_v20_pack.py",
                 "self.assertLess(events.index('sleep-1'),events.index('zoom'))",
                 "self.assertFalse(any(str(e).startswith('sleep-') for e in events))\n                self.assertIn('zoom',events)")
    print("Updated v2.3 regression expectations to instant Zoom")

if __name__=="__main__":
    if sys.argv[1]=="strip":strip_patch()
    elif sys.argv[1]=="tests":update_tests()
    else: raise SystemExit("Usage: strip|tests")
