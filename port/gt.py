"""Reverse-engineering helper for Graviteam Tactics: Mius-Front codelibs (Steam public build 15814271) and the
mpmod1 basic_network.codelib.  Read-only.  Run with:  D:\\programs\\Python312\\python.exe -I gt.py <cmd> ...

Modules are named without extension (adv_game, adv_opgame, ...) or "mod" for the release-2 basic_network.codelib
("modsrc" for the old build compiled from the public source). All addresses are RVAs (hex).

  dis    <module> <rva> [count=40]      disassemble from rva
  func   <module> <rva>                  disassemble the whole function containing rva (.pdata bounds)
  funcs  <module>                        list function starts/ends from .pdata
  find   <module> <hex pattern, ?? = any byte> [--all-sections]
  xref   <module> <rva>                  instructions referencing rva (rip-relative, call/jmp rel32, or absolute
                                         qword in data pointing at it)
  str    <module> <text>                 find ASCII/UTF-16 string and the instructions that reference it
  q      <module> <rva> [count=16]       dump qwords at rva, annotated (module-relative for pointers into the module)
  bytes  <module> <rva> [count=32]       hex bytes at rva
  sect   <module>                        section table and PE timestamp
"""
import functools
import struct
import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

HERE = Path(__file__).resolve().parent
GAME = HERE.parent / "game_test" / "bin" / "rel" / "x64"
MODS = {"mod": HERE.parent / "release" / "mpmod1" / "files" / "bin" / "rel" / "x64" / "basic_network.codelib",
        "modsrc": HERE.parent / "MiusPlayer" / "_mp_research" / "basic_network" / "build" / "basic_network.codelib"}


@functools.lru_cache(None)
def load(name):
    path = MODS.get(name) or (GAME / (name + ".exe" if name == "starter_x64" else name + ".codelib"))
    if name == "starter_x64":
        path = GAME.parent.parent.parent / "starter_x64.exe"
    pe = pefile.PE(str(path), fast_load=False)
    return pe


def image(name):
    pe = load(name)
    return pe, pe.get_memory_mapped_image(), pe.OPTIONAL_HEADER.ImageBase


@functools.lru_cache(None)
def pdata(name):
    pe = load(name)
    out = []
    for rf in getattr(pe, "DIRECTORY_ENTRY_EXCEPTION", []):
        out.append((rf.struct.BeginAddress, rf.struct.EndAddress))
    return sorted(set(out))


def func_bounds(name, rva):
    best = None
    for b, e in pdata(name):
        if b <= rva < e:
            best = (b, e)
    if not best:
        return None
    # chained unwind entries split one function into several ranges: walk to the earliest contiguous start
    b, e = best
    starts = {x for x, _ in pdata(name)}
    return b, e


def cs():
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    return md


def section_of(name, rva):
    pe = load(name)
    for s in pe.sections:
        if s.VirtualAddress <= rva < s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData):
            return s.Name.rstrip(b"\0").decode()
    return "?"


def annotate(name, ins):
    notes = []
    pe, img, base = image(name)
    for op in ins.operands:
        if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
            t = ins.address + ins.size + op.mem.disp
            notes.append(target_note(name, t))
    if ins.mnemonic.startswith(("call", "j")) and ins.operands and ins.operands[0].type == X86_OP_IMM:
        t = ins.operands[0].imm
        fb = func_bounds(name, t)
        if fb and fb[0] == t:
            notes.append("func")
    return "  ; " + "; ".join(n for n in notes if n) if any(notes) else ""


def target_note(name, t):
    pe, img, base = image(name)
    sec = section_of(name, t)
    note = f"{sec}:{t:#x}"
    imp = import_at(name, t)
    if imp:
        return f"[{imp}]"
    if 0 <= t < len(img):
        s = img[t:t + 64]
        z = s.find(b"\0")
        if z > 3 and all(32 <= c < 127 for c in s[:z]):
            return f'{note} "{s[:z].decode()}"'
        if len(s) >= 8 and s[1:2] == b"\0" and s[3:4] == b"\0" and 32 <= s[0] < 127:
            u = img[t:t + 128].decode("utf-16le", "ignore").split("\0")[0]
            if len(u) > 3:
                return f'{note} L"{u}"'
    return note


@functools.lru_cache(None)
def imports(name):
    pe = load(name)
    out = {}
    base = pe.OPTIONAL_HEADER.ImageBase
    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        for imp in entry.imports:
            out[imp.address - base] = f"{entry.dll.decode()}!{imp.name.decode() if imp.name else imp.ordinal}"
    return out


def import_at(name, rva):
    return imports(name).get(rva)


def cmd_dis(name, rva, count=40):
    pe, img, base = image(name)
    n = 0
    for ins in cs().disasm(img[rva:rva + count * 15], rva):
        print(f"{ins.address:#08x}  {bytes(ins.bytes).hex(' '):32s} {ins.mnemonic} {ins.op_str}{annotate(name, ins)}")
        n += 1
        if n >= count:
            break


def cmd_func(name, rva):
    fb = func_bounds(name, rva)
    if not fb:
        print(f"no .pdata function contains {rva:#x}")
        return
    b, e = fb
    print(f"; function {b:#x}-{e:#x} ({e - b} bytes)")
    pe, img, base = image(name)
    for ins in cs().disasm(img[b:e], b):
        print(f"{ins.address:#08x}  {ins.mnemonic} {ins.op_str}{annotate(name, ins)}")


def cmd_funcs(name):
    for b, e in pdata(name):
        print(f"{b:#08x} {e:#08x} {e - b}")


def parse_pat(p):
    toks = p.replace(",", " ").split()
    if len(toks) == 1 and len(toks[0]) > 2:
        t = toks[0]
        toks = [t[i:i + 2] for i in range(0, len(t), 2)]
    return [None if t in ("??", "?") else int(t, 16) for t in toks]


def find_pat(name, pat, all_sections=False):
    pe, img, base = image(name)
    hits = []
    first = next((i for i, b in enumerate(pat) if b is not None), 0)
    anchor = bytes([pat[first]])
    for s in pe.sections:
        if not all_sections and not (s.Characteristics & 0x20000000):
            continue
        lo, hi = s.VirtualAddress, s.VirtualAddress + s.Misc_VirtualSize
        i = img.find(anchor, lo + first, hi)
        while i >= 0:
            st = i - first
            if st + len(pat) <= hi and all(b is None or img[st + k] == b for k, b in enumerate(pat)):
                hits.append(st)
            i = img.find(anchor, i + 1, hi)
    return hits


def cmd_find(name, *pat):
    all_sections = "--all-sections" in pat
    pat = [p for p in pat if p != "--all-sections"]
    hits = find_pat(name, parse_pat(" ".join(pat)), all_sections)
    print(f"{len(hits)} hit(s)")
    for h in hits[:50]:
        fb = func_bounds(name, h)
        print(f"  {h:#08x}  {section_of(name, h)}" + (f"  in func {fb[0]:#x}-{fb[1]:#x} (+{h - fb[0]:#x})" if fb else ""))


@functools.lru_cache(None)
def all_refs(name):
    """Every rip-relative target, call/jmp rel target, of every instruction in every .pdata function."""
    pe, img, base = image(name)
    refs = {}
    md = cs()
    for b, e in pdata(name):
        for ins in md.disasm(img[b:e], b):
            for op in ins.operands:
                t = None
                if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                    t = ins.address + ins.size + op.mem.disp
                elif op.type == X86_OP_IMM and ins.mnemonic.startswith(("call", "j")):
                    t = op.imm
                if t is not None:
                    refs.setdefault(t, []).append((ins.address, f"{ins.mnemonic} {ins.op_str}", b))
    return refs


def cmd_xref(name, rva):
    pe, img, base = image(name)
    hits = all_refs(name).get(rva, [])
    for a, txt, fb in hits[:80]:
        print(f"  code {a:#08x} (func {fb:#x})  {txt}")
    # absolute pointers (vtables, tables) in data
    want = struct.pack("<Q", base + rva)
    i = img.find(want)
    n = 0
    while i >= 0 and n < 40:
        if i % 8 == 0:
            print(f"  data {i:#08x} ({section_of(name, i)}) holds a pointer to it")
            n += 1
        i = img.find(want, i + 1)
    if not hits and not n:
        print("  no references found")


def cmd_str(name, text):
    pe, img, base = image(name)
    for enc, b in (("ascii", text.encode()), ("utf16", text.encode("utf-16le"))):
        i = img.find(b)
        while i >= 0:
            st = i
            if enc == "ascii":
                while st > 0 and 32 <= img[st - 1] < 127:
                    st -= 1
            else:
                while st > 1 and img[st - 2:st] != b"\0\0" and 32 <= img[st - 2] < 127 and img[st - 1] == 0:
                    st -= 2
            s = img[st:st + 120]
            shown = s.split(b"\0")[0].decode("latin1") if enc == "ascii" else s.decode("utf-16le", "ignore").split("\0")[0]
            print(f"{enc} string at {st:#08x} ({section_of(name, st)}): {shown!r}")
            for a, txt, fb in all_refs(name).get(st, [])[:30]:
                print(f"     ref {a:#08x} in func {fb:#x}: {txt}")
            i = img.find(b, i + 1)


def cmd_q(name, rva, count=16):
    pe, img, base = image(name)
    for k in range(count):
        v = struct.unpack_from("<Q", img, rva + 8 * k)[0]
        note = ""
        if base <= v < base + len(img):
            r = v - base
            fb = func_bounds(name, r)
            note = f"-> {name}+{r:#x} ({section_of(name, r)})" + (" func start" if fb and fb[0] == r else "")
        print(f"{rva + 8 * k:#08x}: {v:016x} {note}")


def cmd_bytes(name, rva, count=32):
    pe, img, base = image(name)
    print(img[rva:rva + count].hex(" "))


def cmd_sect(name):
    pe = load(name)
    print(f"timestamp {pe.FILE_HEADER.TimeDateStamp:#x} imagebase {pe.OPTIONAL_HEADER.ImageBase:#x} size {pe.OPTIONAL_HEADER.SizeOfImage:#x}")
    for s in pe.sections:
        print(f"  {s.Name.rstrip(b'\0').decode():8s} rva {s.VirtualAddress:#08x} vsize {s.Misc_VirtualSize:#08x} raw {s.PointerToRawData:#08x}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    cmd, name, *rest = sys.argv[1:]
    name = name.replace(".codelib", "")
    conv = []
    for r in rest:
        try:
            conv.append(int(r, 16))
        except ValueError:
            conv.append(r)
    f = globals()["cmd_" + cmd]
    if cmd in ("find", "str"):
        f(name, *rest) if cmd == "find" else f(name, " ".join(rest))
    else:
        f(name, *conv)


if __name__ == "__main__":
    main()
