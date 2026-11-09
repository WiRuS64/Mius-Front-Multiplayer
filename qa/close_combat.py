"""Brings the two forces of a versus battle within firing range (test helper, used during deployment):
close_combat.py <tools dir> <pid of the joiner's game> [metres=200] [host unit prefix=08]

Moves the JOINER's units (in the joiner's game, their owner) so that its force stands <metres> from the host's force,
in the direction it already lies, keeping its formation. Only soldiers on foot are moved: vehicles and crews stay
where they are, because a vehicle written at a guessed height stays in the ground (seen by the owner 2026-11-09: a PzV
half buried) and there is no way to read the ground's height from outside. The static MG nest is left alone as well.
Writes only into the test game given by pid.
"""
import math
import struct
import sys
import time

sys.path.insert(0, sys.argv[1])
import objs  # noqa: E402
import peek  # noqa: E402
import poke  # noqa: E402

STATIC = '100884a'    # uid of the MG nest (mg_pznest) and its crew in the test battle


def read_units(h):
    out = []
    for p, name, _ in objs.objects(h):
        if name.startswith('i_human') or name.startswith('i_techn'):
            out.append((p, name, struct.unpack('<3f', peek.read(h, p + 0x1b0, 12))))
    return out


def main():
    pid = int(sys.argv[2])
    dist = float(sys.argv[3]) if len(sys.argv) > 3 else 200
    prefix = sys.argv[4] if len(sys.argv) > 4 else '08'
    h, hw = peek.open_proc(pid), poke.open_rw(pid)
    units = read_units(h)
    host = [u for u in units if u[1].rsplit('_', 1)[1].startswith(prefix)]
    join = [u for u in units if not u[1].rsplit('_', 1)[1].startswith(prefix) and STATIC not in u[1]]
    if not host or not join:
        print('close: no units (host %d, joiner %d)' % (len(host), len(join)))
        sys.exit(1)
    ca = [sum(u[2][i] for u in host) / len(host) for i in (0, 2)]
    cb = [sum(u[2][i] for u in join) / len(join) for i in (0, 2)]
    d = math.hypot(cb[0] - ca[0], cb[1] - ca[1])
    ux, uz = (cb[0] - ca[0]) / d, (cb[1] - ca[1]) / d
    dx, dz = ca[0] + ux * dist - cb[0], ca[1] + uz * dist - cb[1]
    cars = [u for u in units if u[1].startswith('i_techn')]
    moved = 0
    for p, name, pos in join:
        if name.startswith('i_techn') or any(math.dist((pos[0], pos[2]), (c[2][0], c[2][2])) < 4 for c in cars):
            continue                # vehicles and their crews stay where they are: a vehicle cannot be put on the ground from outside
        nx, nz = pos[0] + dx, pos[2] + dz
        y = min(host, key=lambda u: (u[2][0] - nx) ** 2 + (u[2][2] - nz) ** 2)[2][1] + 0.5
        poke.write(hw, p + 0x1b0, struct.pack('<3f', nx, y, nz))
        moved += 1
    print('close: %d joiner units moved %.0f m; forces were %.0f m apart, now %.0f m (host %d units)'
          % (moved, math.hypot(dx, dz), d, dist, len(host)))


if __name__ == '__main__':
    main()
