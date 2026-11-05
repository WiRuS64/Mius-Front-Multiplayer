"""How many trenches does each running game have, and how many of them lie twice in the same place?

  python -I trench_dups.py <tools dir with objs.py/peek.py> <pid> [<pid> ...]

Reads the trench manager (i_trencher) the way MiusPlayer's tools\\trench_diff.py does: 0x900 map cells of 0x40
bytes from object +0x2f0, each with a list of 0x70-byte records (pointer at cell +0x20, count at cell +0x2c); a
record starts with the trench's position (x, height, z) and the floats after it describe how it lies. A trench
that is stamped into the ground a second time in the same place shows up as a second record with the same
position and lie ("doubled"). Read-only.
"""
import struct
import sys

sys.path.insert(0, sys.argv[1])
import objs  # noqa: E402
import peek  # noqa: E402


def records(pid):
    h = peek.open_proc(pid)
    tr = [p for p, n, _ in objs.objects(h) if n.startswith('i_trencher')]
    if not tr:
        return None
    cells = peek.read(h, tr[0] + 0x2f0, 0x900 * 0x40)
    if not cells:
        return None
    out = []
    for k in range(0x900):
        ptr, _, count, cap = struct.unpack_from('<QIII', cells, k * 0x40 + 0x20)
        if not ptr or count == 0 or count > 4096 or count > cap:
            continue
        data = peek.read(h, ptr, count * 0x70)
        if not data:
            continue
        for i in range(count):
            f = struct.unpack_from('<12f', data, i * 0x70)
            if all(abs(x) < 1e7 for x in f[:3]) and (abs(f[0]) > 0.01 or abs(f[2]) > 0.01):
                out.append((k, f))
    return out


def main():
    for pid in map(int, sys.argv[2:]):
        r = records(pid)
        if r is None:
            print(f'pid {pid}: no trench manager')
            continue
        seen = {}
        for k, f in r:
            seen.setdefault((k,) + tuple(round(x, 2) for x in f[:3]) + tuple(round(x, 1) for x in f[4:12]), []).append(f)
        doubled = sum(len(v) - 1 for v in seen.values() if len(v) > 1)
        most = max((len(v) for v in seen.values()), default=0)
        print(f'pid {pid}: {len(r)} trenches, {len(seen)} places, doubled {doubled}, most in one place {most}')


if __name__ == '__main__':
    main()
