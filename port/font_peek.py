"""Look at one of the game's bitmap fonts: decode its texture's alpha (DXT5) and draw a sample line with its
fontmap, both into .bmp files. Read-only; nothing of the game is copied anywhere but the given output folder.

  python -I font_peek.py <data_loc.flatdata> <font, e.g. handw_med> <output folder> [sample text]
"""
import struct
import sys
from pathlib import Path


def entries(d):
    out = {}
    o = 0x40
    while o + 0x80 <= len(d) and o < 0x400000:
        _, _, off, size = struct.unpack_from("<IIQQ", d, o)
        name = d[o + 0x20:o + 0x40].split(b"\0")[0]
        typ = d[o + 0x40:o + 0x60].split(b"\0")[0]
        if name and typ and all(32 <= c < 127 for c in name + typ):
            out[(name.decode(), typ.decode())] = (off, size)
        o += 0x80
    return out


def dxt5_alpha(data, w, h):
    a = bytearray(w * h)
    bw, bh = (w + 3) // 4, (h + 3) // 4
    for by in range(bh):
        for bx in range(bw):
            blk = data[(by * bw + bx) * 16:(by * bw + bx) * 16 + 8]
            a0, a1 = blk[0], blk[1]
            bits = int.from_bytes(blk[2:8], "little")
            if a0 > a1:
                pal = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
            else:
                pal = [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]
            for i in range(16):
                x, y = bx * 4 + i % 4, by * 4 + i // 4
                if x < w and y < h:
                    a[y * w + x] = pal[(bits >> (3 * i)) & 7]
    return a


def save_gray(path, pix, w, h):
    row = (w + 3) & ~3
    pal = b"".join(bytes((i, i, i, 0)) for i in range(256))
    body = b"".join(bytes(pix[y * w:(y + 1) * w]).ljust(row, b"\0") for y in range(h - 1, -1, -1))
    hdr = struct.pack("<2sIHHI", b"BM", 54 + 1024 + len(body), 0, 0, 54 + 1024)
    info = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 8, 0, len(body), 2835, 2835, 256, 0)
    Path(path).write_bytes(hdr + info + pal + body)


def main():
    pack, font, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    sample = sys.argv[4] if len(sys.argv) > 4 else "СЕТЕВАЯ ИГРА  Multiplayer 0123"
    d = Path(pack).read_bytes()
    e = entries(d)
    toff, tsize = e.get((f"font_{font}_fnt", "texture")) or e[(f"ucfont_{font}_fnt", "texture")]
    moff, msize = e[(font, "fontmap")]
    tex = d[toff:toff + tsize]
    w, h = tex[0x89] << 8, tex[0x8B] << 8
    print(f"texture {tex[:8]} {w}x{h}, fontmap {msize} bytes")
    if tex[4:8] == b"DXT5":
        alpha = dxt5_alpha(tex[0x2000:], w, h)
    else:                                   # RGB8: 4 bytes a pixel, coverage in the 4th
        px = tex[0x2000:0x2000 + 4 * w * h]
        print("first pixels", px[:32].hex(" "), "channel maxima", [max(px[i::4]) for i in range(4)])
        alpha = bytearray(px[3::4])
    save_gray(out / f"{font}_atlas.bmp", alpha, w, h)
    fm = d[moff:moff + msize]
    glyphs = {}
    for c in range(256):
        adv, cell, bw, bh = struct.unpack_from("<4f", fm, 0x40 + c * 32)
        u0, v0, u1, v1 = struct.unpack_from("<4H", fm, 0x40 + c * 32 + 16)
        glyphs[c] = (adv, cell, u0 * w / 32768, v0 * h / 32768, u1 * w / 32768, v1 * h / 32768)
    print("A:", glyphs[0x41], "space:", glyphs[0x20])
    text = sample.encode("cp1251")
    cell = int(glyphs[0x41][1] + 1)
    width = int(sum(glyphs[c][0] for c in text)) + 8
    img = bytearray(width * cell)
    x = 4.0
    for c in text:
        adv, _, u0, v0, u1, v1 = glyphs[c]
        for yy in range(int(v1 - v0)):
            for xx in range(int(u1 - u0)):
                sx, sy = int(u0) + xx, int(v0) + yy
                dx = int(x) + xx
                if 0 <= dx < width and yy < cell and sx < w and sy < h:
                    img[yy * width + dx] = max(img[yy * width + dx], alpha[sy * w + sx])
        x += adv
    save_gray(out / f"{font}_sample.bmp", img, width, cell)


if __name__ == "__main__":
    main()
