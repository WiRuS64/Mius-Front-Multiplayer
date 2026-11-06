"""Do a vehicle's turret/gun node handles travel in the unit state?  turret_probe.py <tools dir> <pid host> <pid joiner>
[host unit prefix=08]

A vehicle (i_techn) keeps an array of 0x160-byte entries at [+0x18d0] (count at +0x18dc); each holds two renderer
node handles at +0xa8 / +0xac (-1 = none) that adv_physic+0x40cd8 passes to the renderer every frame (the crash of
2026-11-06 14:27 in basic_render+0x12ffd came from there). The script prints those handles for every vehicle in
both games, then, in the host's copy of one joiner vehicle, sets the first handle to -1 (the game skips -1) and
reads it again 2 s later: if it is back, the next state load wrote the joiner's number over it.
"""
import struct
import sys
import time

sys.path.insert(0, sys.argv[1])
import objs  # noqa: E402
import peek  # noqa: E402
import poke  # noqa: E402


def turrets(h):
    out = {}
    for p, name, _ in objs.objects(h):
        if not name.startswith('i_techn'):
            continue
        hdr = peek.read(h, p + 0x18d0, 16)
        if not hdr:
            continue
        arr, = struct.unpack_from('<Q', hdr, 0)
        n, = struct.unpack_from('<I', hdr, 12)
        if not arr or not 0 < n <= 32:
            out[name] = (p, arr, [])
            continue
        hs = []
        for i in range(n):
            d = peek.read(h, arr + 0x160 * i + 0xa8, 8)
            hs.append(struct.unpack('<ii', d) if d else None)
        out[name] = (p, arr, hs)
    return out


def main():
    host_pid, join_pid = int(sys.argv[2]), int(sys.argv[3])
    prefix = sys.argv[4] if len(sys.argv) > 4 else '08'
    ha, hb = peek.open_proc(host_pid), peek.open_proc(join_pid)
    a, b = turrets(ha), turrets(hb)
    differ = 0
    target = None
    for name in sorted(set(a) & set(b)):
        owner = 'host' if name.rsplit('_', 1)[1].startswith(prefix) else 'joiner'
        ta, tb = a[name][2], b[name][2]
        same = ta == tb
        differ += not same
        print('%-26s %-6s host %s | joiner %s%s' % (name, owner, ta, tb, '' if same else '   DIFFER'))
        if owner == 'joiner' and ta and ta[0] and ta[0][0] != -1 and target is None:
            target = name
    print('vehicles with turret entries in both games: %d, differing: %d' % (len(set(a) & set(b)), differ))
    if not target:
        print('POKE: no joiner vehicle with a turret handle - nothing poked')
        return
    p, arr, hs = a[target]
    addr = arr + 0xa8
    before = hs[0][0]
    hw = poke.open_rw(host_pid)
    ok = poke.write(hw, addr, struct.pack('<i', -1))
    time.sleep(2)
    after, = struct.unpack('<i', peek.read(ha, addr, 4))
    print('POKE %s entry 0 +0xa8: was %#x, wrote -1 (%s), 2 s later %#x -> %s' % (
        target, before & 0xffffffff, 'ok' if ok else 'FAILED', after & 0xffffffff,
        'PUT BACK by the state load' if after == before else ('kept' if after == -1 else 'changed to another value')))


if __name__ == '__main__':
    main()
