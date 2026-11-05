"""A very small linker: lays one MSVC x64 COFF object (cl /c /GS- /Zl) into a byte blob that will sit at a fixed
rva inside the mod's image, and resolves its relocations there.

  link(obj_bytes, base_rva, imports, fixed) -> (blob, symbols)

imports: {"GetProcAddress": iat_rva, ...} - the mod's own import slots. "__imp_X" resolves to X's slot; a direct
call to an imported function X (the compiler's memset, say) gets a "jmp [slot]" thunk in the blob.
fixed: {"mp_log": rva, ...} - functions of the mod itself. "__ImageBase" is rva 0.
Kept: .text*, .rdata*, .data*, .bss* (bss as zeros). Dropped: .pdata/.xdata (no unwind info), debug, directives.
Refused: absolute 64-bit relocations (they would need base relocations), unknown symbols, unknown relocation types.
"""
import struct
import sys

KEEP = (b".text", b".rdata", b".data", b".bss")
DROP = (b".pdata", b".xdata", b".debug", b".drectve", b".chks64", b".voltbl", b".gfids", b".gljmp", b".giats")
REL32 = {4: 0, 5: 1, 6: 2, 7: 3, 8: 4, 9: 5}     # IMAGE_REL_AMD64_REL32 .. REL32_5: extra distance to the next instr
ADDR32NB = 3


def _name(raw, strtab):
    if raw[:4] == b"\0\0\0\0":
        off = struct.unpack_from("<I", raw, 4)[0]
        return strtab[off:strtab.index(b"\0", off)]
    return raw.rstrip(b"\0")


def link(obj, base_rva, imports, fixed):
    machine, nsec, _, symptr, nsym, opt, _ = struct.unpack_from("<HHIIIHH", obj, 0)
    if machine != 0x8664 or opt:
        sys.exit("refused: not an x64 object file")
    strtab = obj[symptr + 18 * nsym:]
    secs = []
    for i in range(nsec):
        h = 20 + 40 * i
        name = _name(obj[h:h + 8], strtab) if obj[h] != ord("/") else strtab[int(obj[h + 1:h + 8].rstrip(b"\0")):].split(b"\0")[0]
        size, raw, rel, _, nrel, _, flags = struct.unpack_from("<IIIIHHI", obj, h + 16)
        align = 1 << (((flags >> 20) & 0xF) - 1) if (flags >> 20) & 0xF else 16
        secs.append(dict(name=name, size=size, raw=raw, rel=rel, nrel=nrel, flags=flags, align=align, keep=False))

    syms = []
    i = 0
    while i < nsym:
        s = symptr + 18 * i
        name = _name(obj[s:s + 8], strtab)
        value, secno, typ, cls, naux = struct.unpack_from("<IhHBB", obj, s + 8)
        syms.append(dict(name=name.decode("latin-1"), value=value, sec=secno, cls=cls))
        syms.extend([None] * naux)
        i += 1 + naux

    # layout: thunks first (filled in below), then the kept sections
    blob = bytearray()
    for sec in secs:
        if sec["name"].startswith(DROP) or not sec["name"].startswith(KEEP) or sec["flags"] & 0x800:   # LNK_REMOVE
            continue
        sec["keep"] = True
    used = set()        # symbols the kept sections refer to (others, such as _fltused, are only markers)
    for sec in secs:
        if sec["keep"]:
            for k in range(sec["nrel"]):
                used.add(struct.unpack_from("<I", obj, sec["rel"] + 10 * k + 4)[0])
    need_thunk = sorted({syms[i]["name"] for i in used if syms[i]["sec"] == 0
                         and not syms[i]["name"].startswith("__imp_") and syms[i]["name"] not in fixed
                         and syms[i]["name"] != "__ImageBase"})
    thunks = {}
    for n in need_thunk:
        if n not in imports:
            sys.exit(f"refused: '{n}' is neither defined in the object nor imported by the mod")
        thunks[n] = len(blob)
        slot = imports[n]
        blob += b"\xff\x25" + struct.pack("<i", slot - (base_rva + len(blob) + 6)) + b"\xcc\xcc"
    # uninitialized data last, so it ends the blob and need not be stored in the file
    for sec in sorted(secs, key=lambda x: bool(x["flags"] & 0x80)):
        if not sec["keep"]:
            continue
        while len(blob) % sec["align"]:
            blob += b"\xcc" if sec["flags"] & 0x20 else b"\0"
        sec["at"] = len(blob)
        if sec["flags"] & 0x80:            # uninitialized data
            blob += bytes(sec["size"])
        else:
            blob += obj[sec["raw"]:sec["raw"] + sec["size"]]

    def rva_of(idx):
        s = syms[idx]
        if s["sec"] > 0:
            sec = secs[s["sec"] - 1]
            if not sec["keep"]:
                sys.exit(f"refused: symbol {s['name']} lives in a dropped section {sec['name']}")
            return base_rva + sec["at"] + s["value"]
        n = s["name"]
        if n.startswith("__imp_"):
            if n[6:] not in imports:
                sys.exit(f"refused: the mod does not import {n[6:]}")
            return imports[n[6:]]
        if n in fixed:
            return fixed[n]
        if n == "__ImageBase":
            return 0
        if n in thunks:
            return base_rva + thunks[n]
        sys.exit(f"refused: unresolved symbol {n}")

    for sec in secs:
        if not sec["keep"]:
            continue
        for k in range(sec["nrel"]):
            va, symidx, typ = struct.unpack_from("<IIH", obj, sec["rel"] + 10 * k)
            at = sec["at"] + va
            target = rva_of(symidx)
            addend = struct.unpack_from("<i", blob, at)[0]
            if typ in REL32:
                p = base_rva + at + 4 + REL32[typ]
                struct.pack_into("<i", blob, at, target + addend - p)
            elif typ == ADDR32NB:
                struct.pack_into("<I", blob, at, target + addend)
            else:
                sys.exit(f"refused: relocation type {typ} in {sec['name']} (an absolute address?)")

    out = {}
    for s in syms:
        if s and s["sec"] > 0 and s["cls"] == 2 and secs[s["sec"] - 1]["keep"]:
            out[s["name"]] = base_rva + secs[s["sec"] - 1]["at"] + s["value"]
    return bytes(blob), out
