"""Append the .mpfix section (nest_fix.asm + ping.asm + menu_fix.asm + text.c with fixes.c) to the ported release 2
and redirect nine sites to it.

  python -I build_mpfix.py <ported basic_network.codelib> <output>            (needs ml64.exe: set ML64 to its path)
  python -I build_mpfix.py --blob mpfix.bin <ported> <output>                 (use an already built section)

Building text.c needs cl.exe: MSVC_SETUP is the path of a script that sets up the x64 compiler environment
(vcvars64.bat or the portable setup_x64.bat).

The input must be the output of apply_patch.py with spec_public_15814271.json (SHA-256 checked). The input file is
never written. Section layout (rva 63000h, read/write/execute):

  +000h nest_fix   from mod rva 1d182h: "lea rcx, [r15+1d0h]" (7 bytes) -> call; nop; nop
  +200h ping_rx    from mod rva 169e1h: "movzx ecx, byte [rsi+4]; mov [5b908h], r13d" (11 bytes) -> call; 6 nop
  +400h ping_draw  from mod rva 2ce0dh: "call 24820h" (5 bytes) -> call ping_draw (which ends with jmp 24820h)
  +700h data (16 bytes, zero)
  +780h menu_fix   from mod rva 2bcb6h: "cmp dword ptr [rax+1200h], r15d" (7 bytes) -> call; nop; nop: the main menu
                   is recognised after an operation; a joining player who leaves the map goes back to the lobby
                   (+7f0h / +7f4h: its two state values)
  +800h text: a jump table to text.c's mp_CreateFontA, mp_GetTextExtentPoint32A, mp_TextOutA (8 bytes each), then
        text.c linked by link_coff.py. Sites in the mod's text_tex (rva 2b2b8h), each "call [import]" (6 bytes)
        -> call +800h / +808h / +810h; nop. text.c draws the texts in the game's language (lang_ru.txt) and font.
        +818h mp_state_load_keep (fixes.c) from mod rva 2f092h: "call 2eca4h" (state_load, 5 bytes): a vehicle
        keeps its own model and turret/gun render handles when the other game's state is loaded.
        +820h mp_log_path (fixes.c) from mod rva 2757h: "call 18ech" (sprintf_s of the log file name): logs go
        to the mp_logs folder of the game.
"""
import hashlib
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ML64 = Path(os.environ.get("ML64", r"D:\programs\msvc_build\msvc\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\ml64.exe"))
MSVC_SETUP = Path(os.environ.get("MSVC_SETUP", r"D:\programs\msvc_build\msvc\setup_x64.bat"))
INPUT_SHA = "6218ff0bb70d0ec5e4627a8031f311f453c79aed8272a879347df4c5ea58a90b"
SEC_NAME, SEC_RVA = b".mpfix\0\0", 0x63000
SEC_SIZE = 0x800
DATA = (0x700, 0x710)
MENU, MENU_DATA = 0x780, 0x7F0
TEXT = 0x800                    # jump table, then text.c
TEXT_ENTRIES = ["mp_CreateFontA", "mp_GetTextExtentPoint32A", "mp_TextOutA", "mp_state_load_keep", "mp_log_path",
                "mp_host_map_frame", "mp_on_screen_asked", "mp_session_status", "mp_local_ip", "mp_no_share_log", "mp_numbers_due", "mp_numbers_received", "mp_handles_ok"]
MOD_FUNCS = {"mp_log": 0x27DC,   # what text.c uses of the mod: its log function
             "state_load": 0x2ECA4,   # fixes.c: the mod's state_load
             "menu_controller_of": 0x143F0, "operation_on_screen": 0x17BC8, "session_status": 0x1DAA0,   # fixes.c: the turn watchdog
             "g_tactical": 0x5B618, "g_connected": 0x5B61B, "g_map_collect": 0x5B72C, "g_turn_done": 0x5B72F,
             "g_peer_on_map": 0x5B839, "g_map_in_hash": 0x5BA24, "g_map_collect_since": 0x5BBCC,
             "g_map_restart_at": 0x5BD40, "g_map_note": 0x5BD50,
             "handles_match": 0x2E7E0,   # fixes.c: the guard of unit states
             "xlate_received": 0x39A40, "shots_queue": 0x34C74,   # fixes.c: the other game's numbers
             "g_their_desc": 0x5D3C0, "g_their_obj": 0x5D3D8, "g_expect_desc": 0x5D480, "g_expect_obj": 0x5D484,
             "g_xlate_ready": 0x5D490, "g_xlate_due": 0x5D492,
             "g_ui_scale": 0x5CBD8}   # and its UI scale (float)
# font faces text.c tries, in this order: the game's own (registered by the game in its process), then Windows ones
FACES = ["Segoe Print"]
# (site rva, bytes there now, stub offset in the section, length to replace)
SITES = [
    (0x1d182, bytes.fromhex("49 8d 8f d0 01 00 00"), 0x000),
    (0x169e1, bytes.fromhex("0f b6 4e 04 44 89 2d 1c 4f 04 00"), 0x200),
    (0x2ce0d, bytes.fromhex("e8 0e 7a ff ff"), 0x400),
    (0x2bcb6, bytes.fromhex("44 39 b8 00 12 00 00"), 0x780),   # main menu check -> menu_fix
    (0x2f092, bytes.fromhex("e8 0d fc ff ff"), 0x818),   # state_load -> mp_state_load_keep
    (0x2757, bytes.fromhex("e8 90 f1 ff ff"), 0x820),    # sprintf_s of the log name -> mp_log_path
    (0x11989, bytes.fromhex("e8 62 2a 00 00"), 0x828),   # menu_controller_of in the host's map frame -> turn watchdog
    (0x1a734, bytes.fromhex("e8 8f d4 ff ff"), 0x830),   # operation_on_screen where the joiner answers -> says why not
    (0x2c8db, bytes.fromhex("e8 c0 11 ff ff"), 0x838),   # session_status (the top line) -> shows our note for 12 s
    (0x10693, bytes.fromhex("e8 7e f6 02 00"), 0x840),   # inet_ntop in find_local_ip -> a VPN's address is not shown as this PC's
    (0x1b680, bytes.fromhex("e8 57 71 fe ff"), 0x848),   # mp_log of "map: not shared" -> the host is told as well
    (0x398e8, bytes.fromhex("80 3d a3 3b 02 00 00"), 0x850),   # xlate_frame's "send due?" -> asks for the other game's table if missing
    (0x3506c, bytes.fromhex("e8 cf 49 00 00"), 0x858),   # xlate_received in the shots' dispatch -> sees the request
    (0x31a13, bytes.fromhex("e8 c8 cd ff ff"), 0x860),   # handles_match before a unit state is loaded -> groups renumbered
    (0x2b4b2, bytes.fromhex("ff 15 90 8b 01 00"), 0x800),   # CreateFontA
    (0x2b4eb, bytes.fromhex("ff 15 3f 8b 01 00"), 0x808),   # GetTextExtentPoint32A
    (0x2b5d9, bytes.fromhex("ff 15 29 8a 01 00"), 0x810),   # TextOutA
]
# plain byte changes in the mod's own code: (rva, bytes there now, new bytes)
BYTE_PATCHES = [
    # trench: the other game's list of trenches "stamped outside any dig" (the ones the game stamps by itself
    # when it builds the battle, e.g. an operation's field works) is no longer stamped here a second time.
    # Both games build the battle from the same description and stamp those themselves; stamping the other
    # game's copies on top dug the same trench again, deeper each time (je -> jmp to the end of the loop,
    # where the received list is emptied).
    (0x37be0, bytes.fromhex("0f 84 2e 01 00 00"), bytes.fromhex("e9 2f 01 00 00 90")),
    # the two bytes after the call that replaced the 7-byte cmp at 398e8h: test al, al (the jne after it stays)
    (0x398ed, bytes.fromhex("90 90"), bytes.fromhex("84 c0")),
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
    for name in ("nest_fix", "ping", "menu_fix"):
        obj = HERE / f"{name}.obj"
        subprocess.run([str(ML64), "/nologo", "/c", f"/Fo{obj}", str(HERE / f"{name}.asm")], check=True, cwd=HERE)
        parts[name] = text_of(obj)
    nest, ping, menu = parts["nest_fix"], parts["ping"], parts["menu_fix"]
    if len(nest) > 0x200 or any(ping[:0x200]):
        sys.exit("refused: nest_fix is over 200h bytes or ping.asm has code below 200h")
    if not DATA[0] < len(ping) <= DATA[1] or any(ping[DATA[0]:]):
        sys.exit(f"refused: ping.asm is {len(ping):#x} bytes, the data at 700h must be zero")
    if not MENU < len(menu) <= MENU_DATA or any(menu[:MENU]):
        sys.exit("refused: menu_fix.asm must start at 780h and end before its data at 7f0h")
    blob = bytearray(ping.ljust(SEC_SIZE, b"\0"))
    blob[:len(nest)] = nest
    blob[MENU:len(menu)] = menu[MENU:]
    return bytes(blob)


def c_string(data):
    out = []
    for b in data:
        c = chr(b)
        out.append(c if 32 <= b < 127 and c not in '"\\?' else f"\\{b:03o}")
    return "".join(out)


def text_header():
    """lang_ru.txt -> text_ru.h (k_ru: English and Russian in turn, Windows-1251; FACES)."""
    lines = [l.rstrip("\r") for l in (HERE / "lang_ru.txt").read_text(encoding="utf-8").split("\n")]
    pairs, block = [], []
    for l in lines + [""]:
        if l.startswith("#"):
            continue
        if l.strip() == "":
            if block:
                if len(block) != 2:
                    sys.exit(f"refused: lang_ru.txt: an entry of {len(block)} lines: {block!r}")
                pairs.append(tuple(block))
            block = []
        else:
            block.append(l)
    seen = set()
    blob = b""
    for en, ru in pairs:
        if en in seen:
            sys.exit(f"refused: lang_ru.txt: {en!r} twice")
        seen.add(en)
        specs = len(re.findall(r"%[-+ #0]*\d*(?:\.\d*)?[lhzIjtL]*[a-zA-Z]", en.replace("%%", "")))
        used = [int(n) for n in re.findall(r"%([1-9])", ru.replace("%%", ""))]
        if any(n > specs for n in used):
            sys.exit(f"refused: lang_ru.txt: {ru!r} uses a value {en!r} does not have")
        try:
            blob += en.encode("ascii") + b"\0" + ru.encode("cp1251") + b"\0"
        except UnicodeEncodeError as e:
            sys.exit(f"refused: lang_ru.txt: {en!r}: {e}")
    blob += b"\0"
    faces = "".join(f + "\\0" for f in FACES)
    rows = [blob[i:i + 60] for i in range(0, len(blob), 60)]
    text = ("/* made by build_mpfix.py from lang_ru.txt - do not edit */\n"
            f"static const char k_ru[{len(blob)}] =\n" + "\n".join(f'    "{c_string(r)}"' for r in rows) + ";\n"
            f'#define FACES L"{faces}"\n')
    (HERE / "text_ru.h").write_text(text, encoding="ascii", newline="\n")
    print(f"lang_ru.txt: {len(pairs)} entries, {len(blob)} bytes")


def build_text(imports):
    """text.c -> the code at TEXT: jump table + linked object."""
    sys.path.insert(0, str(HERE))   # python -I leaves the script folder out
    import link_coff
    text_header()
    obj = HERE / "text.obj"
    cmd = f'call "{MSVC_SETUP}" >nul && cl /nologo /c /O1 /GS- /Gs1000000 /Zl /MD /W4 /wd4100 /Fo"{obj}" text.c'
    subprocess.run(cmd, shell=True, check=True, cwd=HERE)
    base = SEC_RVA + TEXT + 8 * len(TEXT_ENTRIES)
    code, syms = link_coff.link(obj.read_bytes(), base, imports, MOD_FUNCS)
    table = bytearray()
    for name in TEXT_ENTRIES:
        if name not in syms:
            sys.exit(f"refused: text.c does not define {name}")
        at = SEC_RVA + TEXT + len(table)
        table += b"\xe9" + struct.pack("<i", syms[name] - (at + 5)) + b"\xcc" * 3
    print(f"text.c: {len(code):#x} bytes at rva {base:#x}")
    return bytes(table) + code


def mod_imports(data):
    """{function name: import slot rva} of the input module."""
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    opt = pe + 24
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    table = opt + struct.unpack_from("<H", data, pe + 20)[0]

    def off(rva):
        for i in range(nsec):
            vsize, va, rsize, rptr = struct.unpack_from("<IIII", data, table + 40 * i + 8)
            if va <= rva < va + max(vsize, rsize):
                return rptr + rva - va
        sys.exit(f"refused: rva {rva:#x} is in no section")

    imp_rva = struct.unpack_from("<I", data, opt + 112 + 8)[0]
    out = {}
    d = off(imp_rva)
    while True:
        oft, _, _, name, ft = struct.unpack_from("<IIIII", data, d)
        if not name:
            break
        k = 0
        while True:
            ent = struct.unpack_from("<Q", data, off(oft or ft) + 8 * k)[0]
            if not ent:
                break
            if not ent >> 63:
                n = off(ent + 2)
                out[data[n:data.index(b"\0", n)].decode()] = ft + 8 * k
            k += 1
        d += 20
    return out


def check_blob(blob):
    if len(blob) <= TEXT + 8 * len(TEXT_ENTRIES) or any(blob[TEXT + 8 * i] != 0xE9 for i in range(len(TEXT_ENTRIES))):
        sys.exit(f"refused: section blob ({len(blob):#x} bytes) has no text.c jump table at {TEXT:#x}")
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
        blob = assemble() + build_text(mod_imports(data))
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
    stored = blob.rstrip(b"\0")       # trailing zeros (text.c's buffers) are not stored: the loader zero-fills them
    raw_size = (len(stored) + file_align - 1) // file_align * file_align
    hdr = SEC_NAME + struct.pack("<IIIIIIHHI", len(blob), SEC_RVA, raw_size, raw_ptr, 0, 0, 0, 0,
                                 0xE0000020)   # code, execute, read, write (the ping state lives at +700h)
    data[new_hdr:new_hdr + 40] = hdr
    struct.pack_into("<H", data, pe + 6, nsec + 1)
    struct.pack_into("<I", data, opt + 56, SEC_RVA + (len(blob) + sec_align - 1) // sec_align * sec_align)
    data += stored.ljust(raw_size, b"\0")

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
