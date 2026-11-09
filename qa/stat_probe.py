"""Compares the battle statistics of two running games and counts fallen units:
stat_probe.py <tools dir> <pid host> <pid joiner> [size=0x1800]

Reads the engine object i_statistic in both games, prints which dwords differ, and the number of soldiers per owner
with a status flag set (same field as combat_diff.py). Read-only: it opens both processes for reading.
"""
import struct
import sys

sys.path.insert(0, sys.argv[1])
import combat_diff  # noqa: E402
import objs  # noqa: E402
import peek  # noqa: E402


def stat_object(h):
    found = [p for p, name, _ in objs.objects(h) if name.startswith('i_statistic')]
    return found[0] if found else None


def main():
    ha, hb = peek.open_proc(int(sys.argv[2])), peek.open_proc(int(sys.argv[3]))
    size = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0x1800
    pa, pb = stat_object(ha), stat_object(hb)
    print('i_statistic: host %s, joiner %s' % (pa and hex(pa), pb and hex(pb)))
    if pa and pb:
        a, b = peek.read(ha, pa, size), peek.read(hb, pb, size)
        n = min(len(a or b''), len(b or b'')) // 4
        diffs = []
        for i in range(n):
            x, y = struct.unpack_from('<I', a, i * 4)[0], struct.unpack_from('<I', b, i * 4)[0]
            if x != y and not (x >> 32 or (0x7ff0 <= x >> 16 <= 0x7fff) or (0x7ff0 <= y >> 16 <= 0x7fff)):
                diffs.append((i * 4, x, y))
        small = [d for d in diffs if d[1] < 100000 and d[2] < 100000]
        print('dwords differing: %d, of them small integers: %d' % (len(diffs), len(small)))
        for off, x, y in small[:60]:
            print('  +%04x host %d joiner %d' % (off, x, y))
    ua, ub = combat_diff.units(ha), combat_diff.units(hb)
    for label, u in (('host', ua), ('joiner', ub)):
        men = {n: v for n, v in u.items() if n.startswith('i_human')}
        flag = sum(1 for v in men.values() if v[0] != bytes(2))
        print('%s: %d soldiers, %d with a status flag, %d vehicles' % (label, len(men), flag, len(u) - len(men)))


if __name__ == '__main__':
    main()
