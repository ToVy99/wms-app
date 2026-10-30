"""Normalize station code local variable for v1.5 zoom insertion."""
from pathlib import Path
p = Path("scan_build/automation.py")
s = p.read_text(encoding="utf-8")
fixes = {
    '            code=cfg.get("check_station_id" if lane=="CHECK" else "pack_station_id","")':
      '            station_code = cfg.get("check_station_id" if lane == "CHECK" else "pack_station_id", "")',
    '            if code and code.strip():':
      '            if station_code and station_code.strip():',
    '                    _enter_station(driver,code,lambda msg: status(f"{lane}: {msg}"))':
      '                    _enter_station(driver,station_code,lambda msg: status(f"{lane}: {msg}"))',
}
for before, after in fixes.items():
    assert s.count(before) == 1, ("Expected a single station marker", before, s.count(before))
    s=s.replace(before, after)
p.write_text(s, encoding="utf-8")
