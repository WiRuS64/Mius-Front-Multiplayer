"""Static check of a basic_network.codelib against a game folder: every memcmp(module+X, sig, n) and every
install_detour(module+X, n, hook) the mod does, found by tracking registers linearly through each function.

  python -I verify_sites.py <basic_network.codelib> <game bin/rel/x64 dir>

For memcmp: OK if the game's bytes at module+X equal the mod's signature.
For detours: OK if n ends on an instruction boundary of the game's code and no copied instruction is rip-relative or
a relative branch (the trampoline copies the bytes as they are).
"""
import struct
import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG, X86_REG_RIP

MEMCMP, DETOUR = 0x414d8, 0x121e4  # release 2 helper functions (memcmp, install_detour)
_md = Cs(CS_ARCH_X86, CS_MODE_64)


def reg64(r):
    n = _md.reg_name(r)
    if n[0] == "e" and len(n) == 3:
        return "r" + n[1:]
    if n[0] == "r" and n[-1] in "dwb" and n[1:-1].isdigit():
        return n[:-1]
    return n


def main():
    mod = pefile.PE(sys.argv[1])
    game = Path(sys.argv[2])
    img = mod.get_memory_mapped_image()
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    imports = {i.address - mod.OPTIONAL_HEADER.ImageBase: (i.name or b"").decode()
               for e in mod.DIRECTORY_ENTRY_IMPORT for i in e.imports}
    games = {}

    def gimg(name):
        if name not in games:
            games[name] = pefile.PE(str(game / name)).get_memory_mapped_image()
        return games[name]

    def cstr(rva):
        s = img[rva:rva + 64]
        return s[:s.find(b"\0")].decode("ascii", "replace")

    funcs = sorted({(r.struct.BeginAddress, r.struct.EndAddress) for r in mod.DIRECTORY_ENTRY_EXCEPTION})
    bad = n = 0
    for b, e in funcs:
        R = {}
        for ins in md.disasm(img[b:e], b):
            ops = ins.operands
            name = reg64
            if ins.mnemonic == "lea" and ops[1].type == X86_OP_MEM:
                m = ops[1].mem
                dst = name(ops[0].reg)
                if m.base == X86_REG_RIP:
                    R[dst] = ("rip", ins.address + ins.size + m.disp)
                elif m.base and name(m.base) in R and m.index == 0:
                    src = R[name(m.base)]
                    if src[0] == "mod":
                        R[dst] = ("addr", src[1], m.disp)
                    elif src[0] == "imm":
                        R[dst] = ("imm", src[1] + m.disp)
                    else:
                        R.pop(dst, None)
                else:
                    R.pop(dst, None)
            elif ins.mnemonic == "mov" and len(ops) == 2 and ops[0].type == X86_OP_REG:
                dst = name(ops[0].reg)
                if ops[1].type == X86_OP_IMM:
                    R[dst] = ("imm", ops[1].imm)
                elif ops[1].type == X86_OP_REG and name(ops[1].reg) in R:
                    R[dst] = R[name(ops[1].reg)]
                else:
                    R.pop(dst, None)
            elif ins.mnemonic == "add" and ops[0].type == X86_OP_REG and ops[1].type == X86_OP_IMM:
                dst = name(ops[0].reg)
                if dst in R and R[dst][0] == "mod":
                    R[dst] = ("addr", R[dst][1], ops[1].imm)
            elif ins.mnemonic == "call":
                t = None
                if ops[0].type == X86_OP_IMM:
                    t = ops[0].imm
                elif ops[0].type == X86_OP_MEM and ops[0].mem.base == X86_REG_RIP:
                    t = imports.get(ins.address + ins.size + ops[0].mem.disp)
                rcx, rdx, r8 = R.get("rcx"), R.get("rdx"), R.get("r8")
                if t == "GetModuleHandleA" and rcx and rcx[0] == "rip":
                    R = {k: v for k, v in R.items() if k in ("rbx", "rsi", "rdi", "rbp", "r12", "r13", "r14", "r15")}
                    R["rax"] = ("mod", cstr(rcx[1]))
                    continue
                if t == MEMCMP and rcx and rcx[0] == "addr" and rdx and rdx[0] == "rip" and r8 and r8[0] == "imm":
                    n += 1
                    want = img[rdx[1]:rdx[1] + r8[1]]
                    got = gimg(rcx[1])[rcx[2]:rcx[2] + r8[1]]
                    ok = want == got
                    bad += not ok
                    print(f"{'OK ' if ok else 'BAD'} memcmp  {rcx[1]}+{rcx[2]:#x} len {r8[1]}  (mod {ins.address:#x})"
                          + ("" if ok else f"\n      sig  {want.hex(' ')}\n      game {got.hex(' ')}"))
                elif t == DETOUR and rcx and rcx[0] == "addr" and R.get("rdx", (0,))[0] == "imm":
                    n += 1
                    ln = R["rdx"][1]
                    code = gimg(rcx[1])[rcx[2]:rcx[2] + 40]
                    pos, why = 0, ""
                    for gi in md.disasm(code, rcx[2]):
                        if pos >= ln:
                            break
                        if any(o.type == X86_OP_MEM and o.mem.base == X86_REG_RIP for o in gi.operands) or \
                                gi.mnemonic.startswith(("j", "call", "loop")):
                            why = f"position-dependent {gi.mnemonic} {gi.op_str} at {gi.address:#x}"
                        pos += gi.size
                    if pos != ln and not why:
                        why = f"length {ln} splits an instruction (boundary at {pos})"
                    bad += bool(why)
                    print(f"{'BAD' if why else 'OK '} detour  {rcx[1]}+{rcx[2]:#x} len {ln}  (mod {ins.address:#x}) {why}")
                for k in ("rax", "rcx", "rdx", "r8", "r9", "r10", "r11"):
                    R.pop(k, None)
            elif ops and ops[0].type == X86_OP_REG and ins.mnemonic not in ("cmp", "test", "push"):
                R.pop(name(ops[0].reg), None)
    print(f"\n{n} sites, {bad} bad")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
