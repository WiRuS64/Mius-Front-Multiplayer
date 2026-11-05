"""Small minidump reader: exception, registers, modules, and return-address candidates on the faulting thread's stack.

  python -I dumpinfo.py <minidump.dmp>
"""
import struct
import sys

d = open(sys.argv[1], "rb").read()
sig, ver, nstreams, dir_rva = struct.unpack_from("<IIII", d, 0)
assert sig == 0x504D444D, "not a minidump"
streams = {}
for i in range(nstreams):
    t, size, rva = struct.unpack_from("<III", d, dir_rva + 12 * i)
    streams.setdefault(t, []).append((size, rva))


def mstr(rva):
    n = struct.unpack_from("<I", d, rva)[0]
    return d[rva + 4:rva + 4 + n].decode("utf-16le")


mods = []
for size, rva in streams.get(4, []):
    n = struct.unpack_from("<I", d, rva)[0]
    for i in range(n):
        m = rva + 4 + 108 * i
        base, msize, _, ts, name_rva = struct.unpack_from("<QIIII", d, m)
        mods.append((base, msize, mstr(name_rva).split("\\")[-1], ts))
mods.sort()


def where(a):
    for base, size, name, _ in mods:
        if base <= a < base + size:
            return f"{name}+{a - base:#x}"
    return None


mem = []   # (start, bytes)
for size, rva in streams.get(5, []):
    n = struct.unpack_from("<I", d, rva)[0]
    for i in range(n):
        start, dsize, drva = struct.unpack_from("<QII", d, rva + 4 + 16 * i)
        mem.append((start, d[drva:drva + dsize]))
for size, rva in streams.get(9, []):
    n, base_rva = struct.unpack_from("<QQ", d, rva)
    off = base_rva
    for i in range(n):
        start, dsize = struct.unpack_from("<QQ", d, rva + 16 + 16 * i)
        mem.append((start, d[off:off + dsize]))
        off += dsize


def read(a, n):
    for start, b in mem:
        if start <= a and a + n <= start + len(b):
            return b[a - start:a - start + n]
    return None


print("modules:")
for base, size, name, ts in mods:
    print(f"  {base:#018x} {size:#9x} {name}")
REGS = "rax rcx rdx rbx rsp rbp rsi rdi r8 r9 r10 r11 r12 r13 r14 r15".split()
for size, rva in streams.get(6, []):
    tid = struct.unpack_from("<I", d, rva)[0]
    code, flags, rec, addr, nparam = struct.unpack_from("<IIQQI", d, rva + 8)
    params = struct.unpack_from("<15Q", d, rva + 8 + 32)[:nparam]
    print(f"\nexception {code:#x} at {addr:#x} ({where(addr)}) thread {tid} params {[hex(p) for p in params]}")
    csize, crva = struct.unpack_from("<II", d, rva + 8 + 152)
    ctx = d[crva:crva + csize]
    regs = struct.unpack_from("<16Q", ctx, 0x78)
    rip = struct.unpack_from("<Q", ctx, 0xF8)[0]
    print(f"rip {rip:#x} {where(rip)}")
    for n, v in zip(REGS, regs):
        print(f"  {n:4} {v:#018x} {where(v) or ''}")
    code_bytes = read(rip - 32, 64)
    if code_bytes:
        print("code at rip-32:", code_bytes.hex(" "))
    rsp = regs[4]
    print("\nstack return-address candidates:")
    for k in range(0, 0x1800, 8):
        b = read(rsp + k, 8)
        if b is None:
            break
        v = struct.unpack("<Q", b)[0]
        w = where(v)
        if w and not w.endswith(".dll+0x0"):
            print(f"  rsp+{k:#06x} {v:#018x} {w}")
