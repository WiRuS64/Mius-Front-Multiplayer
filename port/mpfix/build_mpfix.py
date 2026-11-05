"""Append the .mpfix section (nest_fix.asm + ping.asm + keep_handles.asm) to the ported release 2 and redirect four
sites to it.

  python -I build_mpfix.py <ported basic_network.codelib> <output>            (needs ml64.exe: set ML64 to its path)
  python -I build_mpfix.py --blob mpfix.bin <ported> <output>                 (use an already assembled section)

The input must be the output of apply_patch.py with spec_public_15814271.json (SHA-256 checked). The input file is
never written. Section layout (rva 63000h, read/write/execute):

  +000h nest_fix   from mod rva 1d182h: "lea rcx, [r15+1d0h]" (7 bytes) -> call; nop; nop
  +200h ping_rx    from mod rva 169e1h: "movzx ecx, byte [rsi+4]; mov [5b908h], r13d" (11 bytes) -> call; 6 nop
  +400h ping_draw  from mod rva 2ce0dh: "call 24820h" (5 bytes) -> call ping_draw (which ends with jmp 24820h)
  +700h data (16 bytes, zero)
  +780h keep_handles from mod rva 2f092h: "call 2eca4h" (state_load, 5 bytes) -> call keep_handles
"""
import hashlib
import os
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ML64 = Path(os.environ.get("ML64", r"D:\programs\msvc_build\msvc\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\ml64.exe"))
INPUT_SHA = "6218ff0bb70d0ec5e4627a8031f311f453c79aed8272a879347df4c5ea58a90b"
SEC_NAME, SEC_RVA = b".mpfix\0\0", 0x63000
SEC_SIZE = 0x800
DATA = (0x700, 0x710)
KEEP = 0x780
# (site rva, bytes there now, stub offset in the section, length to replace)
SITES = [
    (0x1d182, bytes.fromhex("49 8d 8f d0 01 00 00"), 0x000),
    (0x169e1, bytes.fromhex("0f b6 4e 04 44 89 2d 1c 4f 04 00"), 0x200),
    (0x2ce0d, bytes.fromhex("e8 0e 7a ff ff"), 0x400),
    (0x2f092, bytes.fromhex("e8 0d fc ff ff"), 0x780),
]
# plain byte changes in the mod's own code: (rva, bytes there now, new bytes)
BYTE_PATCHES = [
    # trench: the other game's list of trenches "stamped outside any dig" (the ones the game stamps by itself
    # when it builds the battle, e.g. an operation's field works) is no longer stamped here a second time.
    # Both games build the battle from the same description and stamp those themselves; stamping the other
    # game's copies on top dug the same trench again, deeper each time (je -> jmp to the end of the loop,
    # where the received list is emptied).
    (0x37be0, bytes.fromhex("0f 84 2e 01 00 00"), bytes.fromhex("e9 2f 01 00 00 90")),
]
# each stub's call/pop that finds the image base (the stubs subtract these fixed offsets)
PC_CHECKS = [
    (0x000, bytes.fromhex("53 e8 00 00 00 00 5b")),          # push rbx; call; pop rbx      -> base + 63006h
    (0x200, bytes.fromhex("41 53 e8 00 00 00 00 41 5b")),    # push r11; call; pop r11      -> base + 63207h
    (0x400, bytes.fromhex("55 e8 00 00 00 00 5d")),          # push rbp; call; pop rbp      -> base + 63406h
    (0x780, bytes.fromhex("53 e8 00 00 00 00 5b")),          # push rbx; call; pop rbx      -> base + 63786h
]


def text_of(obj):
    d = obj.read_bytes()
    nsec = struct.unpack_from("<H", d, 2)[0]
    opt = struct.unpack_from("<H", d, 16)[0]
    for i in range(nsec):
        s = 20 + opt + 40 * i
        name = d[s:s + 8].rstrip(b"\0")
        size, raw = struct.unpack_from("<II", d, s + 16)
        nrel = struct.unpack_from("<H", d, s + 32)[0]
        if name.startswith(b".text"):
            if nrel:
                sys.exit(f"refused: {obj.name} has {nrel} relocations")
            return d[raw:raw + size] if raw else bytes(size)
    sys.exit(f"no .text in {obj.name}")


def assemble():
    parts = {}
    for name in ("nest_fix", "ping", "keep_handles"):
        obj = HERE / f"{name}.obj"
        subprocess.run([str(ML64), "/nologo", "/c", f"/Fo{obj}", str(HERE / f"{name}.asm")], check=True, cwd=HERE)
        parts[name] = text_of(obj)
    nest, ping, keep = parts["nest_fix"], parts["ping"], parts["keep_handles"]
    if len(nest) > 0x200 or any(ping[:0x200]):
        sys.exit("refused: nest_fix is over 200h bytes or ping.asm has code below 200h")
    if not DATA[0] < len(ping) <= DATA[1] or any(ping[DATA[0]:]):
        sys.exit(f"refused: ping.asm is {len(ping):#x} bytes, the data at 700h must be zero")
    if not KEEP < len(keep) <= SEC_SIZE or any(keep[:KEEP]):
        sys.exit("refused: keep_handles.asm must start at 780h and fit the section")
    blob = bytearray(ping.ljust(SEC_SIZE, b"\0"))
    blob[:len(nest)] = nest
    blob[KEEP:len(keep)] = keep[KEEP:]
    return bytes(blob)


def check_blob(blob):
    if len(blob) != SEC_SIZE:
        sys.exit(f"refused: section blob is {len(blob):#x} bytes, expected {SEC_SIZE:#x}")
    for off, want in PC_CHECKS:
        if blob[off:off + len(want)] != want:
            sys.exit(f"refused: the stub at +{off:#x} does not start with its call/pop")
    if blob[:0x200].rstrip(b"\0")[-8:] != SITES[0][1] + b"\xc3":
        sys.exit("refused: nest_fix does not end with the replaced lea + ret")
    if any(blob[DATA[0]:DATA[1]]):
        sys.exit("refused: data area not zero")


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
        (HERE / "mpfix.bin").write_bytes(blob)
    check_blob(blob)

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
                                 0xE0000020)   # code, execute, read, write (the ping state lives at +700h)
    data[new_hdr:new_hdr + 40] = hdr
    struct.pack_into("<H", data, pe + 6, nsec + 1)
    struct.pack_into("<I", data, opt + 56, SEC_RVA + (len(blob) + sec_align - 1) // sec_align * sec_align)
    data += blob.ljust(raw_size, b"\0")

    for rva, want, off in SITES:
        site = None
        for i in range(nsec):
            s = table + 40 * i
            vsize, va, rsize, rptr = struct.unpack_from("<IIII", data, s + 8)
            if va <= rva < va + vsize:
                site = rptr + rva - va
        if bytes(data[site:site + len(want)]) != want:
            sys.exit(f"refused: site {rva:#x} holds {data[site:site + len(want)].hex(' ')}")
        rel = SEC_RVA + off - (rva + 5)
        data[site:site + len(want)] = b"\xe8" + struct.pack("<i", rel) + b"\x90" * (len(want) - 5)
        print(f"site {rva:#x} ({len(want)} bytes) -> call .mpfix+{off:#x}")
    for rva, want, new in BYTE_PATCHES:
        site = None
        for i in range(nsec):
            s = table + 40 * i
            vsize, va, rsize, rptr = struct.unpack_from("<IIII", data, s + 8)
            if va <= rva < va + vsize:
                site = rptr + rva - va
        if len(new) != len(want) or bytes(data[site:site + len(want)]) != want:
            sys.exit(f"refused: patch {rva:#x} holds {data[site:site + len(want)].hex(' ')}")
        data[site:site + len(want)] = new
        print(f"patch {rva:#x}: {want.hex(' ')} -> {new.hex(' ')}")
    dst.write_bytes(data)
    print(f"section {len(blob):#x} bytes at rva {SEC_RVA:#x}")
    print(f"output {dst} SHA-256 {hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
