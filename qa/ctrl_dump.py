"""Dump the menu controller (i_opgame:opgame +0x100) dwords: ctrl_dump.py <tools dir> <pid> [from=0x1100] [to=0x1300]"""
import struct
import sys
sys.path.insert(0, sys.argv[1])
import objs  # noqa: E402
import peek  # noqa: E402

h = peek.open_proc(int(sys.argv[2]))
lo = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x1100
hi = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0x1300
for p, name, _ in objs.objects(h):
    if name == 'i_opgame:opgame':
        c, = struct.unpack('<Q', peek.read(h, p + 0x100, 8))
        d = peek.read(h, c + lo, hi - lo)
        for i in range(0, hi - lo, 4):
            print('%#06x %d' % (lo + i, struct.unpack_from('<i', d, i)[0]))
        break
