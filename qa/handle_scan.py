"""Where does a unit keep renderer handles?  handle_scan.py <tools dir> <pid> [objman hex] [shift]   (reads memory only)

A unit's part list ([+0x850], count +0x85c, 0x60-byte records) holds its renderer handles at +0x48 / +0x4c
(group << 10 | node). Every other value in the unit, or in a block it points to, that names the same renderer group
is another handle. Those are what must stay local when the other game's state is loaded. Prints, per class of unit,
the places found and in how many of the units they were found.

With a shift (the MP_TEST_SHIFT_GROUPS of the test), it looks instead for values naming a unit's group moved by that
much, i.e. the other game's numbering left in the unit, and ends with "foreign: <n> values in <m> units". Only places
where at least 3 units of the class hold one of their own handles count: anything else is a chance match of unrelated
memory (1 to 4 values were seen in runs where nothing was loaded), listed but not counted.
"""
import collections
import struct
import sys

sys.path.insert(0, sys.argv[1])
import objs  # noqa: E402
import peek  # noqa: E402

SIZES = {'i_human': 0x2400, 'i_techn': 0x3800}
SUB = 0x1800   # how much of a pointed-to block is looked at


def read(h, a, n):
    """as much of [a, a+n) as can be read, in 0x1000 pieces cut at page limits"""
    out = bytearray()
    while n > 0:
        k = min(n, 0x1000 - (a & 0xfff))
        d = peek.read(h, a, k)
        if not d:
            break
        out += d
        a += k
        n -= k
    return bytes(out)


def named(v, groups, exact):
    return v in exact or (v > 0x400 and v != 0xffffffff and (v >> 10) in groups)


def scan_unit(h, p, cls, parts, groups, exact, sample):
    """the places in the unit, and in the blocks it points to, holding a value that names one of these groups"""
    d = read(h, p, SIZES[cls])
    seen = set()
    for o in range(0, len(d) - 3, 4):
        v = struct.unpack_from('<I', d, o)[0]
        if named(v, groups, exact):
            seen.add('+%04x' % o)
            sample.setdefault((cls, '+%04x' % o), hex(v))
    for o in range(0, len(d) - 7, 8):
        q = struct.unpack_from('<Q', d, o)[0]
        if not 0x10000 <= q < 0x7fffffff0000 or q & 7 or parts == q or p <= q < p + SIZES[cls]:
            continue
        b = read(h, q, SUB)
        if len(b) < 16:
            continue
        for j in range(0, len(b) - 3, 4):
            v = struct.unpack_from('<I', b, j)[0]
            if named(v, groups, exact):
                key = '[+%04x]+%04x' % (o, j)
                seen.add(key)
                sample.setdefault((cls, key), hex(v))
    return seen


def main():
    pid = int(sys.argv[2])
    if len(sys.argv) > 3:
        objs.OBJMAN = int(sys.argv[3], 16)
    shift = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    h = peek.open_proc(pid)
    all_objs = objs.objects(h)
    found = {k: collections.Counter() for k in SIZES}
    alien = {k: collections.Counter() for k in SIZES}
    count = collections.Counter()
    sample = {}
    for p, name, _ in all_objs:
        cls = name.split(':')[0]
        if cls not in SIZES:
            continue
        hd = read(h, p + 0x850, 16)
        if len(hd) < 16:
            continue
        parts = struct.unpack_from('<Q', hd, 0)[0]
        n = struct.unpack_from('<I', hd, 12)[0]
        if not parts or not 0 < n < 512:
            continue
        rec = read(h, parts, n * 0x60)
        if len(rec) < n * 0x60:
            continue
        exact = set()
        for i in range(n):
            a = struct.unpack_from('<I', rec, i * 0x60 + 0x48)[0]   # node handle (group << 10 | node)
            if a and a != 0xffffffff:
                exact.add(a)
        groups = {v >> 10 for v in exact if v > 0x400}
        count[cls] += 1
        own = scan_unit(h, p, cls, parts, groups, exact, sample)
        for k in own:
            found[cls][k] += 1
        if shift:
            seen = scan_unit(h, p, cls, parts, {g + shift for g in groups}, set(), sample)
            for k in seen:
                alien[cls][k] += 1

    for cls, c in found.items():
        print('=== %s: %d units with a part list' % (cls, count[cls]))
        for k, m in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])):
            if m * 2 >= count[cls]:
                print('  %-16s in %4d units   e.g. %s' % (k, m, sample[(cls, k)]))
    if shift:
        foreign = chance = 0
        for cls, c in alien.items():
            for k, m in sorted(c.items()):
                place = found[cls][k] >= 3   # own handles at this place in 3 units or more
                print('  %s %-16s other numbering in %d units%s' % (cls, k, m, '' if place else '   (not a handle place: chance)'))
                if place:
                    foreign += m
                else:
                    chance += m
        print('foreign: %d values at handle places (%d units looked at), %d chance matches elsewhere'
              % (foreign, sum(count.values()), chance))

main()
