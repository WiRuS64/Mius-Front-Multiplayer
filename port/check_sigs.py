"""Check the byte signatures mpmod1 expects at fixed RVAs against a game folder.

usage: python -I check_sigs.py <game dir>
Prints, per hook site, OK / MISMATCH with the bytes found, plus PE timestamps of each module.
"""
import struct
import sys
from pathlib import Path

# (module, rva, signature hex, what) -- copied from basic_network/*.cpp of MiusPlayer
SITES = [
    ("adv_game.codelib", 0xbec30 + 1, "57 48 83 ec 30 48 8b f9", "AI commander step (session.cpp update_ai_commander)"),
    ("adv_opgame.codelib", 0xd6660, "48 89 5c 24 08 48 89 7c 24 10 55 48 8d ac 24 10 ff ff ff", "op save (session.cpp)"),
    ("adv_opgame.codelib", 0x36b40, "48 89 5c 24 08 57 48 83 ec 30 0f 57 c0 49 8b d8", "next turn (session.cpp)"),
    ("adv_opgame.codelib", 0x76810, "48 8b c4 44 88 40 18 88 50 10 55 56 57 41 56", "turn worker (session.cpp)"),
    ("adv_interf.codelib", 0x3b3b0, "40 53 48 83 ec 40 48 8b d9 80 b9 da 0e 00 00 00", "Start button (session.cpp)"),
    ("adv_interf.codelib", 0x3b4f0, "48 89 5c 24 08 57 48 83 ec 50 49 8b d8 48 8b f9", "input action (session.cpp)"),
    ("adv_interf.codelib", 0x41700, "40 55 48 83 ec 30 8b 81 e8 0d 00 00 48 8b e9", "box result (session.cpp)"),
    ("base_main.codelib", 0x4200, "48 8b c4 48 89 58 08 48 89 70 10 48 89 78 20", "timer step (session.cpp)"),
    ("basic_physic.codelib", 0x18430, "48 89 54 24 10 55 53 56 57 41 54 41 56 48 8d ac 24 e8 fd ff ff", "shell launch (shots.cpp)"),
    ("basic_physic.codelib", 0x19260, "48 89 5c 24 08 57 48 81 ec 70 02 00 00 48 8b f9", "shell explode (shots.cpp)"),
    ("adv_game.codelib", 0xdbc20, "48 8b c4 48 89 58 10 55 56 57 41 54 41 55 41 56 41 57", "trench dig (trench.cpp)"),
    ("adv_physic.codelib", 0x82090, "48 89 5c 24 10 48 89 6c 24 18 56 57 41 54 41 56", "base load (state.cpp)"),
    ("basic_render.codelib", 0x13ab0, "48 89 6c 24 10 48 89 74 24 18 57 48 83 ec 20 4c 8b 89 40 02 00 00", "node lookup (state.cpp)"),
    ("adv_opgame.codelib", 0x627f0, "4c 89 44 24 18 48 89 54 24 10 53 48 83 ec 40 83 b9 58 12 00 00 11", "do_mm_skirmish (ui.cpp)"),
    ("adv_opgame.codelib", 0x2b210, "45 33 c0 ba 02 00 00 00 e9", "do_mm_campaign (ui.cpp)"),
    ("adv_opgame.codelib", 0x2b250, "45 33 c0 ba 03 00 00 00 e9", "do_mm_qbattle (ui.cpp)"),
]


class PE:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        d = self.data
        pe = struct.unpack_from("<I", d, 0x3C)[0]
        assert d[pe:pe + 4] == b"PE\0\0", path
        nsec, self.timestamp = struct.unpack_from("<H", d, pe + 6)[0], struct.unpack_from("<I", d, pe + 8)[0]
        opt_size = struct.unpack_from("<H", d, pe + 20)[0]
        opt = pe + 24
        self.image_size = struct.unpack_from("<I", d, opt + 56)[0]
        self.checksum = struct.unpack_from("<I", d, opt + 64)[0]
        self.sections = []
        for i in range(nsec):
            s = opt + opt_size + i * 40
            name = d[s:s + 8].rstrip(b"\0").decode("ascii", "replace")
            vsize, va, rsize, raw = struct.unpack_from("<IIII", d, s + 8)
            self.sections.append((name, va, vsize, raw, rsize))

    def read(self, rva, n):
        for name, va, vsize, raw, rsize in self.sections:
            if va <= rva < va + max(vsize, rsize):
                off = raw + (rva - va)
                return self.data[off:off + n]
        return b""


def main():
    game = Path(sys.argv[1])
    x64 = game / "bin" / "rel" / "x64"
    mods = {}
    bad = 0
    for mod, rva, sig, what in SITES:
        if mod not in mods:
            mods[mod] = PE(x64 / mod)
        want = bytes.fromhex(sig)
        got = mods[mod].read(rva, len(want))
        ok = got == want
        bad += not ok
        print(f"{'OK      ' if ok else 'MISMATCH'} {mod}+{rva:#x}  {what}" + ("" if ok else f"\n           want {want.hex(' ')}\n           got  {got.hex(' ')}"))
    print()
    for mod, pe in sorted(mods.items()):
        print(f"{mod}: timestamp {pe.timestamp:#x} image {pe.image_size:#x} sections " +
              ", ".join(f"{n}@{va:#x}" for n, va, *_ in pe.sections))
    print(f"\n{len(SITES) - bad}/{len(SITES)} signatures match")


if __name__ == "__main__":
    main()
