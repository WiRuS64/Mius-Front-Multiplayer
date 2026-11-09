"""Write spec_public_15814271.json for apply_patch.py: ports mpmod1 release 2 to Steam public buildid 15814271.

Every address below was mapped with portmap.py from the build the mod was written for (old_build/, extracted from the
author's Ghidra project, SHA-256 equal to the author's game_build_3598.sha256) to the installed public build.
Each code edit replaces one 32-bit immediate/displacement inside one instruction of release 2; the script finds it in
the instruction bytes and refuses if it is not there exactly once.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

import pefile

HERE = Path(__file__).resolve().parent
MOD = HERE.parent / "release" / "mpmod1" / "files" / "bin" / "rel" / "x64" / "basic_network.codelib"
NEW = Path.home() / "Desktop" / "миус тесты" / "bin" / "rel" / "x64"

# (mod instruction rva, old value, new value, why)
IMM = [
    (0x10dfc, 0x3b3b0, 0x3b320, "adv_interf Start..range start (caller check)"),
    (0x10e01, 0x3ba00, 0x3b960, "adv_interf range end (caller check)"),
    (0x123da, 0x3b3b0, 0x3b320, "adv_interf Start button action"),
    (0x123f8, 0x3b4f0, 0x3b460, "adv_interf input action"),
    (0x12402, 0x41700, 0x41630, "adv_interf box result"),
    (0x124a4, 0x57470, 0x57310, "adv_interf 0x57470 (sig check)"),
    (0x124bd, 0x57470, 0x57310, "adv_interf 0x57470 (detour)"),
    (0x101a6, 0x76810, 0x76510, "adv_opgame turn worker"),
    (0x101f0, 0x76810, 0x76510, "adv_opgame turn worker"),
    (0x1a374, 0x76810, 0x76510, "adv_opgame turn worker (hook)"),
    (0x12b1b, 0x35540, 0x353e0, "adv_opgame 0x35540"),
    (0x19837, 0xd6660, 0xd6080, "adv_opgame operation save"),
    (0x1a324, 0x36b40, 0x369e0, "adv_opgame next turn"),
    (0x1a3c0, 0x44120, 0x43f50, "adv_opgame recon (sig check)"),
    (0x1a3da, 0x44120, 0x43f50, "adv_opgame recon (detour)"),
    (0x24601, 0x627f0, 0x624f0, "adv_opgame do_mm_skirmish"),
    (0x2843c, 0x627f0, 0x624f0, "adv_opgame do_mm_skirmish"),
    (0x2a064, 0x627f0, 0x624f0, "adv_opgame do_mm_skirmish"),
    (0x29cf4, 0x66650, 0x66350, "adv_opgame 0x66650"),
    (0x29d37, 0x134698, 0x133698, "adv_opgame dword table {6,10,14,18}"),
    (0x2efc4, 0x82090, 0x82020, "adv_physic base load (sig check)"),
    (0x2efe2, 0x82090, 0x82020, "adv_physic base load (detour)"),
    (0x349b2, 0x9b520, 0x9b4b0, "adv_physic 0x9b520 (sig check)"),
    (0x349cb, 0x9b520, 0x9b4b0, "adv_physic 0x9b520 (detour)"),
    (0x3cfbb, 0xc7a18, 0xc79d8, "adv_physic vtable slot -> +0x43230 (hit sync)"),
    (0x3cfca, 0xc67a0, 0xc6760, "adv_physic vtable slot -> +0x66cc0 (hit sync)"),
    (0x3d000, 0x66cc0, 0x66c90, "adv_physic hit function expected in that slot"),
]
# (mod rva, new bytes from module+rva of the public build, length, why)
SIGS = [
    (0x497a8, "adv_interf", 0x3b460, 16, "input action signature (prologue recompiled: sub rsp,0x40; regs swapped)"),
    (0x48da0, "adv_opgame", 0x369e0, 16, "next turn signature (prologue recompiled)"),
]
# (mod instruction rva, old bytes, new bytes, why)
RAW = [
    (0x1a357, "ba 10 00 00 00", "ba 11 00 00 00",
     "next turn detour length 16 -> 17: new prologue push rbx/sub rsp,20/xorps/mov rbx,rcx/comiss = 17 bytes"),
]


def main():
    pe = pefile.PE(str(MOD))
    img = pe.get_memory_mapped_image()
    data = MOD.read_bytes()
    edits = []
    for rva, old, new, why in IMM:
        ins = img[rva:rva + 15]
        k = ins[:10].find(struct.pack("<I", old))
        if k < 0 or ins[:10].count(struct.pack("<I", old)) != 1:
            sys.exit(f"{rva:#x}: {old:#x} not found once in {ins[:10].hex(' ')}")
        off = pe.get_offset_from_rva(rva + k)
        assert data[off:off + 4] == struct.pack("<I", old)
        edits.append({"file_offset": hex(off), "expect": struct.pack("<I", old).hex(" "),
                      "write": struct.pack("<I", new).hex(" "), "why": f"{why}: {old:#x} -> {new:#x} (mod rva {rva:#x})"})
    for rva, module, at, n, why in SIGS:
        g = pefile.PE(str(NEW / f"{module}.codelib"))
        new = g.get_memory_mapped_image()[at:at + n]
        off = pe.get_offset_from_rva(rva)
        edits.append({"file_offset": hex(off), "expect": data[off:off + n].hex(" "), "write": new.hex(" "),
                      "why": f"{why} (mod rva {rva:#x}, {module}+{at:#x})"})
    for rva, old, new, why in RAW:
        off = pe.get_offset_from_rva(rva)
        assert data[off:off + len(bytes.fromhex(old.replace(' ', '')))] == bytes.fromhex(old.replace(" ", "")), rva
        edits.append({"file_offset": hex(off), "expect": old, "write": new, "why": f"{why} (mod rva {rva:#x})"})
    spec = {"input_sha256": hashlib.sha256(data).hexdigest(), "target": "Steam public, buildid 15814271", "edits": edits}
    out = HERE / "spec_public_15814271.json"
    out.write_text(json.dumps(spec, indent=1))
    print(f"{len(edits)} edits -> {out}")


if __name__ == "__main__":
    main()
