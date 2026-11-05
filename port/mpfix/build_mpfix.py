"""Append the .mpfix section (nest_fix.asm) to the ported release 2 and redirect one instruction to it.

  python -I build_mpfix.py <ported basic_network.codelib> <output>        (needs ml64.exe, see ML64 below)
  python -I build_mpfix.py --blob nest_fix.bin <ported> <output>          (use an already assembled blob)

The input must be the output of apply_patch.py with spec_public_15814271.json (SHA-256 checked). The input file is
never written. At mod rva 0x1d182 the 7-byte "lea rcx, [r15+1d0h]" becomes "call .mpfix; nop; nop"; the stub ends
with that same lea.
"""
import hashlib
import os
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ML64 = Path(os.environ.get("ML64", "ml64.exe"))  # full path of MSVC's ml64.exe, or have it on PATH
INPUT_SHA = "6218ff0bb70d0ec5e4627a8031f311f453c79aed8272a879347df4c5ea58a90b"
SITE_RVA, SITE_BYTES = 0x1d182, bytes.fromhex("49 8d 8f d0 01 00 00")   # lea rcx, [r15+1d0h]
SEC_NAME, SEC_RVA = b".mpfix\0\0", 0x63000


def assemble():
    obj = HERE / "nest_fix.obj"
    subprocess.run([str(ML64), "/nologo", "/c", f"/Fo{obj}", str(HERE / "nest_fix.asm")], check=True, cwd=HERE)
    d = obj.read_bytes()
    nsec = struct.unpack_from("<H", d, 2)[0]
    opt = struct.unpack_from("<H", d, 16)[0]
    for i in range(nsec):
        s = 20 + opt + 40 * i
        name = d[s:s + 8].rstrip(b"\0")
        size, raw, rel, nrel = struct.unpack_from("<I", d, s + 16)[0], struct.unpack_from("<I", d, s + 20)[0], \
            struct.unpack_from("<I", d, s + 24)[0], struct.unpack_from("<H", d, s + 32)[0]
        if name == b".text" or name.startswith(b".text"):
            if nrel:
                sys.exit(f"refused: the stub has {nrel} relocations")
            return d[raw:raw + size]
    sys.exit("no .text in the object")


def main():
    a = sys.argv[1:]
    blob = None
    if a[:1] == ["--blob"]:
        blob = Path(a[1]).read_bytes()
        a = a[2:]
    src, dst = Path(a[0]).resolve(), Path(a[1]).resolve()
    if src == dst:
        sys.exit("refused: the output path is the input path")
    data = bytearray(src.read_bytes())
    if hashlib.sha256(data).hexdigest() != INPUT_SHA:
        sys.exit(f"refused: {src.name} is not the ported release 2 ({INPUT_SHA[:16]}...)")
    if blob is None:
        blob = assemble()
        (HERE / "nest_fix.bin").write_bytes(blob)
    # the stub finds the image base from "push rbx; call getpc; getpc: pop rbx" = 53 E8 00000000 5B
    if blob[:7] != bytes.fromhex("53 e8 00 00 00 00 5b") or blob[-8:] != SITE_BYTES + b"\xc3":
        sys.exit("refused: the stub does not start with push/call/pop or end with the replaced lea + ret")

    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    opt = pe + 24
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    sec_align, file_align = struct.unpack_from("<II", data, opt + 32)
    size_of_image, size_of_headers = struct.unpack_from("<II", data, opt + 56)
    table = opt + opt_size
    new_hdr = table + 40 * nsec
    if new_hdr + 40 > size_of_headers or any(data[new_hdr:new_hdr + 40]):
        sys.exit("refused: no free room for another section header")
    if size_of_image != SEC_RVA:
        sys.exit(f"refused: SizeOfImage is {size_of_image:#x}, expected {SEC_RVA:#x}")
    raw_ptr = len(data)
    assert raw_ptr % file_align == 0
    raw_size = (len(blob) + file_align - 1) // file_align * file_align
    hdr = SEC_NAME + struct.pack("<IIIIIIHHI", len(blob), SEC_RVA, raw_size, raw_ptr, 0, 0, 0, 0,
                                 0x60000020)   # code, execute, read
    data[new_hdr:new_hdr + 40] = hdr
    struct.pack_into("<H", data, pe + 6, nsec + 1)
    struct.pack_into("<I", data, opt + 56, SEC_RVA + (len(blob) + sec_align - 1) // sec_align * sec_align)
    data += blob.ljust(raw_size, b"\xcc")

    # redirect the site
    site = None
    for i in range(nsec):
        s = table + 40 * i
        vsize, va, rsize, rptr = struct.unpack_from("<IIII", data, s + 8)
        if va <= SITE_RVA < va + vsize:
            site = rptr + SITE_RVA - va
    if bytes(data[site:site + 7]) != SITE_BYTES:
        sys.exit(f"refused: site holds {data[site:site + 7].hex(' ')}")
    rel = SEC_RVA - (SITE_RVA + 5)
    data[site:site + 7] = b"\xe8" + struct.pack("<i", rel) + b"\x90\x90"
    dst.write_bytes(data)
    print(f"stub {len(blob)} bytes at rva {SEC_RVA:#x}; site {SITE_RVA:#x} redirected")
    print(f"output {dst} SHA-256 {hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
