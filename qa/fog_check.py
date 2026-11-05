"""Fog of war in a versus battle: fog_check.py <tools dir> <pid host> <pid joiner> [host unit prefix, default 08]

Replaces view_check.py, whose "own unit" flag (+0x6f0) is the unit's place in its player's force and reads 0 for
every unit in a skirmish battle, so it passed or failed by accident.

A unit is drawn while its "seen" countdown (object +0x72c, seconds) is above zero (MiusPlayer state.cpp; the game's
visibility manager refreshes it for the player's own units and for spotted enemies). Checks, in both games:
  - every unit of this game's own player is shown (at least 95 %, leaving room for units just killed);
  - the other player's units are not all shown: some are hidden by the fog of war. The mod's known failure was the
    opposite (a unit loaded with its owner's view values stays visible for good).
"""
import collections
import struct
import sys

sys.path.insert(0, sys.argv[1])
import objs  # noqa: E402
import peek  # noqa: E402


def table(pid, host_prefix):
    h = peek.open_proc(pid)
    c = collections.Counter()
    for p, name, _ in objs.objects(h):
        if name.startswith('i_human') or name.startswith('i_techn'):
            d = peek.read(h, p + 0x72c, 4)
            if d:
                force = 'host' if name.rsplit('_', 1)[1].startswith(host_prefix) else 'joiner'
                c[(force, struct.unpack('<f', d)[0] > 0)] += 1
    return c


def main():
    prefix = sys.argv[4] if len(sys.argv) > 4 else '08'
    ok = True
    for label, pid, own, other in (('host', int(sys.argv[2]), 'host', 'joiner'),
                                   ('joiner', int(sys.argv[3]), 'joiner', 'host')):
        c = table(pid, prefix)
        own_shown, own_all = c[(own, True)], c[(own, True)] + c[(own, False)]
        oth_shown, oth_all = c[(other, True)], c[(other, True)] + c[(other, False)]
        good = own_all > 0 and own_shown >= 0.95 * own_all and oth_all > 0 and oth_shown < oth_all
        ok &= good
        print(f'{label} game: own units shown {own_shown}/{own_all}, other player\'s units shown {oth_shown}/{oth_all}'
              f' -> {"ok" if good else "WRONG"}')
    print('fog: %s' % ('ok' if ok else 'WRONG'))


if __name__ == '__main__':
    main()
