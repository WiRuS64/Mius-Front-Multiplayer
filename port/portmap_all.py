"""Map every RVA-like constant listed in scan_release2_filtered.txt with portmap.py. Read-only."""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import portmap
OLDMODS = {p.stem for p in portmap.OLD.glob("*.codelib")}
func = None
seen = set()
for line in (Path(__file__).parent / "scan_release2_filtered.txt").read_text().splitlines():
    m = re.match(r"func (0x\w+)-\S+ modules (.*)", line)
    if m:
        func, mods = m.group(1), [x[:-8] for x in re.findall(r"'([\w.]+)'", m.group(2))]
        continue
    m = re.search(r"^\s+(0x\w+)\s+(.*?)\s+const (0x\w+)\s+@file (0x\w+)", line)
    if not m:
        continue
    at, ins, c, foff = m.groups()
    c = int(c, 16)
    for mod in mods:
        if mod not in OLDMODS:
            print(f"{func} {at} {foff:>8} {mod:12} {c:#9x} [no old copy]   {ins}")
            continue
        o, n = portmap.mods(mod)
        sec = o.section(c)
        if not sec or c < 0x1000:
            continue
        sec, new, why = portmap.map_any(mod, c)
        flag = "SAME" if new == c else ("MOVED" if new is not None else "??")
        print(f"{func} {at} {foff:>8} {mod:12} {c:#9x} [{sec}] -> {('%#x' % new) if new is not None else 'UNMAPPED':9} {flag:5} {why} | {ins}")
