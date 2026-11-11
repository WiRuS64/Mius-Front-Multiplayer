"""Where in a unit's saved state are renderer handles?  state_dump_scan.py <mp_state_dump.bin>

The dump (MP_TEST_DUMP_STATES=<n>) holds, per state received: u32 size, u32 part count, 48 bytes of the unit's name,
this game's part node handles, the state. A state is packed, so a value naming one of the unit's renderer groups can
sit at any byte offset. This lists, per kind of unit, every place such a value was found: the section of the state
(header, one of the counted lists, the part list) and the offset in it, and in how many states of that kind. A place
found in every state of a kind is a real handle; one found now and then is a chance match of unrelated bytes.
"""
import collections
import struct
import sys

LISTS = [0x11, 8, 0, 4, 0x40, 0x4c]   # after 296h header bytes: counted lists of these record sizes (0: 8 bytes skipped)


def sections(d):
    """[(name, start, record size, count)] of the state, or None"""
    out = [('head', 0, 0x296, 1)]
    pos = 0x296
    for i, r in enumerate(LISTS):
        if not r:
            out.append(('skip', pos, 8, 1))
            pos += 8
            continue
        if pos + 8 > len(d):
            return None
        n = struct.unpack_from('<I', d, pos + 4)[0]
        out.append(('cnt%d' % i, pos, 8, 1))
        pos += 8
        if pos + n * r > len(d):
            return None
        out.append(('list%d/%x' % (i, r), pos, r, n))
        pos += n * r
    out.append(('tail', pos, max(1, len(d) - pos), 1))
    return out


def where(secs, i):
    for name, start, r, n in secs:
        if start <= i < start + r * n:
            return '%s+%x' % (name, (i - start) % r)
    return '?'


def main():
    raw = open(sys.argv[1], 'rb').read()
    pos = 0
    places = collections.defaultdict(collections.Counter)
    states = collections.Counter()
    sizes = collections.defaultdict(set)
    tails = collections.Counter()
    while pos + 56 <= len(raw):
        size, n = struct.unpack_from('<II', raw, pos)
        name = raw[pos + 8:pos + 56].split(b'\0')[0].decode('latin-1')
        pos += 56
        local = struct.unpack_from('<%dI' % n, raw, pos)
        pos += 4 * n
        d = raw[pos:pos + size]
        pos += size
        kind = name.split(':')[0]
        groups = {h >> 10 for h in local if h != 0xffffffff and h >> 10 >= 0x10}
        secs = sections(d)
        states[kind] += 1
        sizes[kind].add(size)
        if not secs:
            tails[kind] += 1
            continue
        seen = set()
        for i in range(len(d) - 3):
            v = struct.unpack_from('<I', d, i)[0]
            if v != 0xffffffff and v >> 10 in groups:
                seen.add(where(secs, i))
        for k in seen:
            places[kind][k] += 1
    for kind in sorted(states):
        print('=== %s: %d states, sizes %s%s' % (kind, states[kind], sorted(sizes[kind])[:6],
                                                 ', %d not parsed' % tails[kind] if tails[kind] else ''))
        for k, m in sorted(places[kind].items(), key=lambda kv: (-kv[1], kv[0])):
            print('  %-24s %4d' % (k, m))


main()
