"""Improve settings layout on compact laptops and show the save controls."""
from pathlib import Path
p = Path(__file__).resolve().parents[2] / "scan_build" / "main.py"
s = p.read_text(encoding="utf-8")
fixes = [
    ('self.root.geometry("940x630")', 'self.root.geometry("940x650")', 1),
    ('def line_entry(parent, variable, size=14, show=None):',
     'def line_entry(parent, variable, size=14, show=None, compact=False):', 1),
    ('entry.pack(fill="x", ipady=11, padx=12)',
     'entry.pack(fill="x", ipady=3 if compact else 11, padx=12)', 1),
    ('def field(host, name, key, default="", secret=False, size=11):',
     'def field(host, name, key, default="", secret=False, size=11, compact=False):', 1),
    ('label(host, name, 10, "bold", MUTED).pack(anchor="w", pady=(0, 5))',
     'label(host, name, 10, "bold", MUTED).pack(anchor="w", pady=(0, 3 if compact else 5))', 1),
    ('line_entry(host, var, size=size, show="●" if secret else None)',
     'line_entry(host, var, size=size, show="●" if secret else None, compact=compact)', 1),
    ('edge.pack(fill="x", pady=(0, 13))',
     'edge.pack(fill="x", pady=(0, 4 if compact else 13))', 1),
    ('field(advanced, title, key, self.cfg.get(key, ""), size=10)',
     'field(advanced, title, key, self.cfg.get(key, ""), size=10, compact=True)', 2),
    ('foot = tk.Frame(win, bg=BG, padx=20, pady=15)',
     'foot = tk.Frame(win, bg=BG, padx=20, pady=12)', 1),
    ('foot.pack(fill="x")',
     'foot.pack(side="bottom", fill="x", before=panel)', 1),
]
for old, new, count in fixes:
    matches = s.count(old)
    if matches != count:
        raise RuntimeError(f"UI patch expected {count}, got {matches}: {old[:40]}")
    s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
print("Compact settings UI applied.")
