/* Mius-Front Multiplayer: the mod's on-screen texts in the game's language and in the game's own fonts.

   The mod draws every text through one function (text_tex, mod rva 2b2b8h): CreateFontA("Segoe Print"),
   GetTextExtentPoint32A, then TextOutA into a 32-bit bitmap that becomes a texture (white, coverage = the
   brightest of B, G, R). build_mpfix.py points those three calls here, through the jump table in front of this
   code. The string the mod passes is English; here it is looked up in the translation table (lang_ru.txt, built
   into text_ru.h).

   Language: MP_LANG=ru|en if set, else what the game chose at start-up: the engine writes its localization
   (loc_rus / loc_eng) into root\engine.txt every time it starts.

   Font: the game's own bitmap fonts, read from the player's game (data\common\<loc>\packed_data\data_loc.flatdata:
   "font_*_fnt" textures, DXT5 or 32-bit, and "fontmap" tables of 256 characters, Windows-1251 order). Bold and
   large texts (titles, buttons, the main menu entry) use the handwriting of the game's main menu (handw), the
   rest the game's standard font (std). Each is scaled so its capitals are as high, and sit where, the mod's
   layout expects (it was made for Segoe Print: capitals 0.78 of the size, the line 1.75 of it, capitals centred
   at 0.51 of the line). If the fonts cannot be read the text is drawn with Windows fonts as before.

   Freestanding: no CRT start-up, nothing that needs base relocations, only functions the mod already imports
   (build_mpfix.py wires their import slots) and what GetProcAddress finds. Built with cl /c /O1 /GS- /Zl /MD. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include "text_ru.h"   /* k_ru[]: "english\0russian (cp1251)\0" ... "\0"; FACES */

void mp_log(const char *fmt, ...);   /* the mod's log (mod rva 27dch), resolved by build_mpfix.py */
extern float g_ui_scale;             /* the mod's UI scale (mod rva 5cbd8h): sizes are nominal * this */

typedef HFONT (WINAPI *CreateFontW_f)(int, int, int, int, int, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD,
                                     LPCWSTR);
typedef BOOL (WINAPI *GetTextExtentPoint32W_f)(HDC, LPCWSTR, int, LPSIZE);
typedef BOOL (WINAPI *TextOutW_f)(HDC, int, int, LPCWSTR, int);
typedef int (WINAPI *EnumFontFamiliesExW_f)(HDC, LPLOGFONTW, FONTENUMPROCW, LPARAM, DWORD);
typedef HGDIOBJ (WINAPI *GetCurrentObject_f)(HDC, UINT);
typedef int (WINAPI *GetObjectW_f)(HANDLE, int, LPVOID);

static int g_ready, g_ru, g_loc_rus;
static CreateFontW_f pCreateFontW;
static GetTextExtentPoint32W_f pExtentW;
static TextOutW_f pTextOutW;
static EnumFontFamiliesExW_f pEnumW;
static GetCurrentObject_f pCurrentObject;
static GetObjectW_f pGetObjectW;
static WCHAR g_face[LF_FACESIZE];
static int g_height, g_weight;
static HFONT g_smaller;          /* Windows-font path: a font made smaller to fit a long translation */
static char g_out[1024];         /* the text to draw (translated or not), its bytes, and its length */
static const char *g_text;
static int g_len;
static WCHAR g_wide[1024];
static int g_wlen;
static char g_root[MAX_PATH];
static float g_fit = 1.0f;      /* game-font path: how much smaller this translation is drawn so it fits */

/* ------------------------------------------------------------------ small helpers (no CRT) */
static int slen(const char *s) { int n = 0; while (s[n]) n++; return n; }
static int wlen(const WCHAR *s) { int n = 0; while (s[n]) n++; return n; }
static int is_digit(char c) { return c >= '0' && c <= '9'; }
static void zero(void *p, size_t n) { volatile char *c = (volatile char *)p; while (n--) *c++ = 0; }
static int same(const char *a, const char *b) { while (*a && *a == *b) { a++; b++; } return *a == *b; }
static void cat(char *d, const char *s) { while (*d) d++; while (*s) *d++ = *s++; *d = 0; }
static const char *find(const char *hay, int n, const char *needle)
{
    int k = slen(needle);
    for (int i = 0; i + k <= n; i++) {
        int j = 0;
        while (j < k && hay[i + j] == needle[j]) j++;
        if (j == k) return hay + i;
    }
    return 0;
}
static int ifloor(float f) { int i = (int)f; return (float)i > f ? i - 1 : i; }
static int iceil(float f) { int i = (int)f; return (float)i < f ? i + 1 : i; }

/* ------------------------------------------------------------------ language */
static void pick_language(void)
{
    char path[MAX_PATH + 32];
    DWORD k = GetModuleFileNameA(0, path, MAX_PATH);
    while (k && path[k - 1] != '\\') k--;
    path[k] = 0;
    for (DWORD i = 0; i <= k; i++) g_root[i] = path[i];
    cat(path, "root\\engine.txt");
    static char buf[4096];
    int got = 0;
    FILE *f = 0;
    if (!fopen_s(&f, path, "rb") && f) { got = (int)fread(buf, 1, sizeof buf, f); fclose(f); }
    g_loc_rus = got > 0 && find(buf, got, "loc_rus") != 0;
    char v[16];
    DWORD n = GetEnvironmentVariableA("MP_LANG", v, sizeof v);
    if (n && n < sizeof v) g_ru = v[0] == 'r' || v[0] == 'R';
    else g_ru = g_loc_rus;
    mp_log("text: language %s (%s)", g_ru ? "Russian" : "English",
           n && n < sizeof v ? "MP_LANG" : got > 0 ? (g_loc_rus ? "root\\engine.txt: loc_rus" : "root\\engine.txt: not loc_rus")
                                                   : "no root\\engine.txt");
}

/* ------------------------------------------------------------------ the game's bitmap fonts */
struct glyph { float adv, u0, v0, u1, v1; };
struct gfont {
    int tried, ok, w, h;
    unsigned char *a;            /* coverage, w * h */
    float cell, cap0, cap1;      /* line height; top and bottom of the capitals (rows of 'H') */
    struct glyph g[256];
};
#define N_FONTS 8
static const char k_font_names[] = "handw_small\0handw_med\0handw_big\0handw_ultra\0std3\0std4\0std5\0std6\0";
#define FIRST_STD 4
static struct gfont g_fonts[N_FONTS];
static char g_pack[MAX_PATH + 64];
static unsigned char g_dir[0x4000];
static int g_dir_ok = -1;

static const char *font_name(int i)
{
    const char *p = k_font_names;
    while (i--) p += slen(p) + 1;
    return p;
}

static int read_at(FILE *f, long off, void *dst, size_t n)
{
    return !fseek(f, off, SEEK_SET) && fread(dst, 1, n, f) == n;
}

/* offset and size of a pack entry (name, type) from the directory read into g_dir */
static int pack_entry(const char *name, const char *type, unsigned *off, unsigned *size)
{
    for (int o = 0x40; o + 0x80 <= (int)sizeof g_dir; o += 0x80) {
        const char *n = (const char *)g_dir + o + 0x20, *t = (const char *)g_dir + o + 0x40;
        if (g_dir[o + 0x20 + 0x1f] || g_dir[o + 0x40 + 0x1f]) continue;
        if (same(n, name) && same(t, type)) {
            *off = *(unsigned *)(g_dir + o + 8);
            *size = *(unsigned *)(g_dir + o + 16);
            return *(unsigned *)(g_dir + o + 12) == 0 && *(unsigned *)(g_dir + o + 20) == 0;
        }
    }
    return 0;
}

static int open_pack(FILE **f)
{
    if (g_dir_ok == 0) return 0;
    const char *locs[2];
    locs[0] = g_loc_rus ? "loc_rus" : "loc_eng";
    locs[1] = g_loc_rus ? "loc_eng" : "loc_rus";
    for (int i = 0; i < 2; i++) {
        g_pack[0] = 0;
        cat(g_pack, g_root);
        cat(g_pack, "data\\common\\");
        cat(g_pack, locs[i]);
        cat(g_pack, "\\packed_data\\data_loc.flatdata");
        *f = 0;
        if (!fopen_s(f, g_pack, "rb") && *f) {
            if (g_dir_ok == 1) return 1;
            if (read_at(*f, 0, g_dir, sizeof g_dir) && g_dir[0] == 'A' && g_dir[1] == 'Z' && g_dir[2] == 'P') {
                g_dir_ok = 1;
                mp_log("text: the game's fonts from %s", g_pack);
                return 1;
            }
            fclose(*f);
        }
    }
    g_dir_ok = 0;
    mp_log("text: the game's fonts not found (data\\common\\loc_*\\packed_data\\data_loc.flatdata); Windows fonts are used");
    return 0;
}

static void dxt5_alpha(const unsigned char *src, unsigned char *a, int w, int h)
{
    int bw = w / 4, bh = h / 4;
    for (int by = 0; by < bh; by++)
        for (int bx = 0; bx < bw; bx++) {
            const unsigned char *b = src + (by * bw + bx) * 16;
            unsigned a0 = b[0], a1 = b[1], pal[8];
            unsigned __int64 bits = 0;
            for (int i = 0; i < 6; i++) bits |= (unsigned __int64)b[2 + i] << (8 * i);
            pal[0] = a0;
            pal[1] = a1;
            if (a0 > a1) for (int i = 1; i < 7; i++) pal[1 + i] = ((7 - i) * a0 + i * a1) / 7;
            else {
                for (int i = 1; i < 5; i++) pal[1 + i] = ((5 - i) * a0 + i * a1) / 5;
                pal[6] = 0;
                pal[7] = 255;
            }
            for (int i = 0; i < 16; i++) a[(by * 4 + i / 4) * w + bx * 4 + i % 4] = (unsigned char)pal[(bits >> (3 * i)) & 7];
        }
}

static struct gfont *load_font(int i)
{
    struct gfont *F = &g_fonts[i];
    if (F->tried) return F->ok ? F : 0;
    F->tried = 1;
    FILE *f;
    if (!open_pack(&f)) return 0;
    char tex_name[48] = "", map_name[32] = "";
    unsigned toff, tsize, moff, msize;
    cat(map_name, font_name(i));
    cat(tex_name, "font_"); cat(tex_name, font_name(i)); cat(tex_name, "_fnt");
    int found = pack_entry(tex_name, "texture", &toff, &tsize);
    if (!found) { tex_name[0] = 0; cat(tex_name, "ucfont_"); cat(tex_name, font_name(i)); cat(tex_name, "_fnt"); found = pack_entry(tex_name, "texture", &toff, &tsize); }
    static unsigned char map[0x2040], head[0x90];
    unsigned char *raw = 0;
    if (found && pack_entry(map_name, "fontmap", &moff, &msize) && msize == sizeof map && read_at(f, (long)moff, map, sizeof map)
        && map[0] == 'A' && map[1] == 'Z' && map[2] == 'F' && map[3] == 'N' && read_at(f, (long)toff, head, sizeof head)
        && head[0] == 'A' && head[1] == 'T' && head[2] == 'F' && head[3] == '1') {
        int w = head[0x89] << 8, h = head[0x8b] << 8, dxt5 = head[4] == 'D' && head[7] == '5', rgb8 = head[4] == 'R' && head[6] == 'B';
        size_t need = (size_t)w * h * (dxt5 ? 1 : 4);
        if (w > 0 && h > 0 && w <= 2048 && h <= 2048 && (dxt5 || rgb8) && 0x2000 + need <= tsize) {
            raw = (unsigned char *)VirtualAlloc(0, need, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
            F->a = (unsigned char *)VirtualAlloc(0, (size_t)w * h, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
            if (raw && F->a && read_at(f, (long)(toff + 0x2000), raw, need)) {
                if (dxt5) dxt5_alpha(raw, F->a, w, h);
                else for (size_t p = 0; p < (size_t)w * h; p++) F->a[p] = raw[p * 4 + 3];
                F->w = w;
                F->h = h;
                for (int c = 0; c < 256; c++) {
                    const float *e = (const float *)(map + 0x40 + c * 32);
                    const unsigned short *u = (const unsigned short *)(map + 0x40 + c * 32 + 16);
                    F->g[c].adv = e[0];
                    F->g[c].u0 = u[0] * (float)w / 32768.0f;
                    F->g[c].v0 = u[1] * (float)h / 32768.0f;
                    F->g[c].u1 = u[2] * (float)w / 32768.0f;
                    F->g[c].v1 = u[3] * (float)h / 32768.0f;
                }
                F->cell = ((const float *)(map + 0x40 + 'H' * 32))[1];
                /* the capitals: rows of 'H' with ink */
                const struct glyph *g = &F->g['H'];
                int top = -1, bottom = -1;
                for (int y = (int)g->v0; y < (int)g->v1 && y < h; y++)
                    for (int x = (int)g->u0; x < (int)g->u1 && x < w; x++)
                        if (F->a[y * w + x] > 100) { if (top < 0) top = y; bottom = y + 1; break; }
                if (top >= 0 && F->cell > 4) {
                    F->cap0 = top - g->v0;
                    F->cap1 = bottom - g->v0;
                    F->ok = 1;
                }
            }
            if (raw) VirtualFree(raw, 0, MEM_RELEASE);
        }
    }
    fclose(f);
    mp_log("text: the game's font %s %s (%dx%d, line %d, capitals %d..%d)", font_name(i), F->ok ? "loaded" : "could NOT be read",
           F->w, F->h, (int)F->cell, (int)F->cap0, (int)F->cap1);
    if (!F->ok && F->a) { VirtualFree(F->a, 0, MEM_RELEASE); F->a = 0; }
    return F->ok ? F : 0;
}

/* the font for the text being drawn, and how it is placed: scale, line height, where the line's top goes */
struct layout { struct gfont *f; float k, top; int line; };
static int layout_for(int px, int bold, struct layout *L)
{
    if (px <= 0) return 0;
    float scale = g_ui_scale > 0.1f ? g_ui_scale : 1.0f;
    int hand = bold || px >= (int)(22 * scale + 0.5f);
    float cap = 0.78f * px;
    int first = hand ? 0 : FIRST_STD, last = hand ? FIRST_STD - 1 : N_FONTS - 1;
    struct gfont *pick = 0;
    /* the smallest font whose capitals are at least as high (drawn smaller is sharper than drawn larger) */
    for (int i = first; i <= last; i++) {
        struct gfont *F = load_font(i);
        if (!F) continue;
        pick = F;
        if (F->cap1 - F->cap0 >= cap) break;
    }
    if (!pick) return 0;
    L->f = pick;
    L->k = cap / (pick->cap1 - pick->cap0) * g_fit;
    L->line = iceil(1.75f * px);
    L->top = 0.51f * L->line - L->k * 0.5f * (pick->cap0 + pick->cap1);
    return 1;
}

static float text_width(const struct layout *L, const unsigned char *s, int n)
{
    float w = 0;
    for (int i = 0; i < n; i++) w += L->f->g[s[i]].adv * L->k;
    return w;
}

static float sample(const struct gfont *F, float x, float y, const struct glyph *g)
{
    /* bilinear, clamped to the glyph's own cell so neighbours in the atlas do not bleed in */
    if (x < g->u0) x = g->u0;
    if (y < g->v0) y = g->v0;
    if (x > g->u1 - 1) x = g->u1 - 1;
    if (y > g->v1 - 1) y = g->v1 - 1;
    int x0 = ifloor(x), y0 = ifloor(y);
    float fx = x - x0, fy = y - y0;
    int x1 = x0 + 1 < F->w ? x0 + 1 : x0, y1 = y0 + 1 < F->h ? y0 + 1 : y0;
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    const unsigned char *a = F->a;
    float top = a[y0 * F->w + x0] * (1 - fx) + a[y0 * F->w + x1] * fx;
    float bot = a[y1 * F->w + x0] * (1 - fx) + a[y1 * F->w + x1] * fx;
    return top * (1 - fy) + bot * fy;
}

/* draws the text into the bitmap selected into dc, white on black, the way TextOutA would have */
static int draw_bitmap_font(HDC dc, int x, int y, const struct layout *L, const unsigned char *s, int n)
{
    DIBSECTION ds;
    HGDIOBJ bmp = pCurrentObject(dc, OBJ_BITMAP);
    if (!bmp || pGetObjectW(bmp, sizeof ds, &ds) != sizeof ds || !ds.dsBm.bmBits || ds.dsBm.bmBitsPixel != 32) return 0;
    int W = ds.dsBm.bmWidth, H = ds.dsBm.bmHeight < 0 ? -ds.dsBm.bmHeight : ds.dsBm.bmHeight;
    /* the mod makes this bitmap top-down (biHeight = -h); GetObject reports the height without the sign */
    unsigned char *bits = (unsigned char *)ds.dsBm.bmBits;
    const struct gfont *F = L->f;
    float pen = (float)x, inv = 1.0f / L->k;
    for (int i = 0; i < n; i++) {
        const struct glyph *g = &F->g[s[i]];
        float adv = g->adv * L->k;
        int c0 = ifloor(pen), c1 = iceil(pen + (g->u1 - g->u0) * L->k);
        int r0 = y + ifloor(L->top), r1 = y + iceil(L->top + (g->v1 - g->v0) * L->k);
        for (int r = r0 < 0 ? 0 : r0; r < r1 && r < H; r++) {
            unsigned char *row = bits + (size_t)r * W * 4;
            for (int c = c0 < 0 ? 0 : c0; c < c1 && c < W; c++) {
                float sum = 0;
                for (int sy = 0; sy < 4; sy++)
                    for (int sx = 0; sx < 4; sx++) {
                        float dx = c + (sx + 0.5f) * 0.25f - pen, dy = r + (sy + 0.5f) * 0.25f - (y + L->top);
                        sum += sample(F, g->u0 + dx * inv - 0.5f, g->v0 + dy * inv - 0.5f, g);
                    }
                int v = (int)(sum / 16.0f + 0.5f);
                if (v > 255) v = 255;
                unsigned char *p = row + c * 4;
                if (v > p[0]) p[0] = p[1] = p[2] = (unsigned char)v;
            }
        }
        pen += adv;
    }
    return 1;
}

/* ------------------------------------------------------------------ Windows fonts (fallback) */
static int CALLBACK font_seen(const LOGFONTW *lf, const TEXTMETRICW *tm, DWORD type, LPARAM found)
{
    (void)lf; (void)tm; (void)type;
    *(int *)found = 1;
    return 0;
}

static void pick_face(void)
{
    static const WCHAR faces[] = FACES;   /* "face\0face\0" from text_ru.h */
    HDC dc = CreateCompatibleDC(0);
    g_face[0] = 0;
    for (const WCHAR *f = faces; *f; f += wlen(f) + 1) {
        LOGFONTW lf;
        int found = 0, j;
        zero(&lf, sizeof lf);
        lf.lfCharSet = DEFAULT_CHARSET;
        for (j = 0; f[j] && j < LF_FACESIZE - 1; j++) lf.lfFaceName[j] = f[j];
        pEnumW(dc, &lf, (FONTENUMPROCW)font_seen, (LPARAM)&found, 0);
        if (found) {
            for (j = 0; f[j] && j < LF_FACESIZE - 1; j++) g_face[j] = f[j];
            g_face[j] = 0;
            break;
        }
    }
    DeleteDC(dc);
}

static HFONT make_font(int height)
{
    return pCreateFontW(height, 0, 0, 0, g_weight, 0, 0, 0, DEFAULT_CHARSET, OUT_TT_PRECIS, CLIP_DEFAULT_PRECIS,
                        ANTIALIASED_QUALITY, DEFAULT_PITCH, g_face[0] ? g_face : L"Segoe Print");
}

static void init(void)
{
    if (g_ready) return;
    g_ready = 1;
    HMODULE gdi = GetModuleHandleA("gdi32.dll");
    pCreateFontW = (CreateFontW_f)GetProcAddress(gdi, "CreateFontW");
    pExtentW = (GetTextExtentPoint32W_f)GetProcAddress(gdi, "GetTextExtentPoint32W");
    pTextOutW = (TextOutW_f)GetProcAddress(gdi, "TextOutW");
    pEnumW = (EnumFontFamiliesExW_f)GetProcAddress(gdi, "EnumFontFamiliesExW");
    pCurrentObject = (GetCurrentObject_f)GetProcAddress(gdi, "GetCurrentObject");
    pGetObjectW = (GetObjectW_f)GetProcAddress(gdi, "GetObjectW");
    if (!pCreateFontW || !pExtentW || !pTextOutW || !pEnumW || !pCurrentObject || !pGetObjectW) {
        mp_log("text: gdi32 functions not found, texts stay as they were");
        return;
    }
    pick_language();
    pick_face();
    char v[8];
    if (GetEnvironmentVariableA("MP_WINDOWS_FONTS", v, sizeof v)) { g_dir_ok = 0; mp_log("text: MP_WINDOWS_FONTS: Windows fonts"); }
    g_ready = 2;
}

/* ------------------------------------------------------------------ translation
   An English entry may hold printf specifications (%s %u %d %.1f %02d ...): each matches any text, also none.
   The Russian entry puts the values back with %1 .. %9 (in the English order); %% is a percent sign. A value is
   itself translated when it is an English entry (names of things the mod passes in: "the host", "Germans" ...).
   An English entry starting with '~' is a fragment: replaced wherever it occurs in a value nothing else matched. */
#define MAX_CAPS 9
struct caps { const char *at[MAX_CAPS]; int len[MAX_CAPS]; int n; };

static const char *spec_end(const char *p)   /* p points at '%' (not "%%"); returns the char after the spec */
{
    p++;
    while (*p == '-' || *p == '+' || *p == ' ' || *p == '#' || *p == '0') p++;
    while (is_digit(*p)) p++;
    if (*p == '.') { p++; while (is_digit(*p)) p++; }
    while (*p == 'l' || *p == 'h' || *p == 'z' || *p == 'I' || *p == 'j' || *p == 't' || *p == 'L') p++;
    return *p ? p + 1 : p;
}

static int match(const char *p, const char *s, struct caps *c)
{
    for (;;) {
        if (p[0] == '%' && p[1] == '%') { if (*s != '%') return 0; p += 2; s++; continue; }
        if (p[0] == '%') {
            const char *q = spec_end(p);
            int k = c->n;
            if (k >= MAX_CAPS) return 0;
            for (const char *e = s;; e++) {
                c->at[k] = s;
                c->len[k] = (int)(e - s);
                c->n = k + 1;
                if (match(q, e, c)) return 1;
                if (!*e) break;
            }
            c->n = k;
            return 0;
        }
        if (*p != *s) return 0;
        if (!*p) return 1;
        p++;
        s++;
    }
}

static int put(char *out, int at, int cap, const char *s, int n)
{
    for (int i = 0; i < n && at < cap - 1; i++) out[at++] = s[i];
    return at;
}

static int translate(const char *s, int n, char *out, int cap, int depth);

/* a value: an entry of its own, else with its fragments replaced, else as it is */
static int put_value(char *out, int at, int cap, const char *s, int n, int depth)
{
    char tmp[512];
    if (n < (int)sizeof tmp && depth < 4) {
        int k = translate(s, n, tmp, sizeof tmp, depth + 1);
        if (k >= 0) return put(out, at, cap, tmp, k);
    }
    for (int i = 0; i < n;) {
        const char *e = k_ru;
        int done = 0;
        while (*e) {
            const char *ru = e + slen(e) + 1;
            if (e[0] == '~') {
                int k = slen(e + 1);
                if (k && i + k <= n) {
                    int j = 0;
                    while (j < k && s[i + j] == e[1 + j]) j++;
                    if (j == k) { at = put(out, at, cap, ru, slen(ru)); i += k; done = 1; break; }
                }
            }
            e = ru + slen(ru) + 1;
        }
        if (!done) at = put(out, at, cap, s + i++, 1);
    }
    return at;
}

/* returns the length written to out, or -1 when no entry matches */
static int translate(const char *s, int n, char *out, int cap, int depth)
{
    char whole[512];
    if (n >= (int)sizeof whole) return -1;
    for (int i = 0; i < n; i++) whole[i] = s[i];
    whole[n] = 0;
    for (const char *e = k_ru; *e;) {
        const char *ru = e + slen(e) + 1;
        struct caps c;
        c.n = 0;
        if (e[0] != '~' && match(e, whole, &c)) {
            int at = 0;
            for (const char *r = ru; *r; r++) {
                if (r[0] == '%' && r[1] == '%') { at = put(out, at, cap, "%", 1); r++; }
                else if (r[0] == '%' && r[1] >= '1' && r[1] <= '9') {
                    int k = r[1] - '1';
                    if (k < c.n) at = put_value(out, at, cap, c.at[k], c.len[k], depth);
                    r++;
                } else at = put(out, at, cap, r, 1);
            }
            out[at] = 0;
            return at;
        }
        e = ru + slen(ru) + 1;
    }
    return -1;
}

/* the text to draw: g_text / g_len (bytes, Windows-1251 when translated), g_wide / g_wlen */
static void prepare(const char *s, int len)
{
    int cp = CP_ACP;
    g_text = s;
    g_len = len;
    if (g_ru) {
        int k = translate(s, len, g_out, sizeof g_out, 0);
        if (k >= 0) { g_text = g_out; g_len = k; cp = 1251; }
    } else {
        /* operations are still being tested (2.6.2): the button says so in English too, as lang_ru.txt does */
        static const char op[] = "HOST AN OPERATION", beta[] = "HOST AN OPERATION (BETA)";
        int i = 0;
        while (i < len && op[i] && s[i] == op[i]) i++;
        if (i == len && i == (int)sizeof op - 1) {
            for (i = 0; beta[i]; i++) g_out[i] = beta[i];
            g_out[i] = 0;
            g_text = g_out;
            g_len = i;
        }
    }
    g_wlen = g_len ? MultiByteToWideChar(cp, 0, g_text, g_len, g_wide, sizeof g_wide / sizeof g_wide[0] - 1) : 0;
    if (g_wlen < 0) g_wlen = 0;
    g_wide[g_wlen] = 0;
}

/* ------------------------------------------------------------------ the three replaced calls */
HFONT WINAPI mp_CreateFontA(int h, int w, int esc, int orient, int weight, DWORD italic, DWORD underline, DWORD strike,
                            DWORD charset, DWORD out_prec, DWORD clip, DWORD quality, DWORD pitch, LPCSTR face)
{
    init();
    if (g_ready != 2)
        return CreateFontA(h, w, esc, orient, weight, italic, underline, strike, charset, out_prec, clip, quality, pitch, face);
    g_height = h;
    g_weight = weight;
    return make_font(h);
}

BOOL WINAPI mp_GetTextExtentPoint32A(HDC dc, LPCSTR s, int len, LPSIZE size)
{
    if (g_ready != 2) return GetTextExtentPoint32A(dc, s, len, size);
    prepare(s, len);
    struct layout L;
    g_fit = 1.0f;
    if (layout_for(g_height < 0 ? -g_height : g_height, g_weight >= FW_BOLD, &L)) {
        if (g_text == g_out) {
            /* a translation much longer than the English text would run out of the box made for it: smaller */
            float ru = text_width(&L, (const unsigned char *)g_text, g_len), en = text_width(&L, (const unsigned char *)s, len);
            /* room: 12% more than the English text, plus about six letters (short labels sit in wide boxes) */
            float room = en * 1.12f + 6.0f * (g_height < 0 ? -g_height : g_height) * 0.55f;
            if (en > 0 && ru > room) {
                g_fit = room / ru;
                if (g_fit < 0.6f) g_fit = 0.6f;
                layout_for(g_height < 0 ? -g_height : g_height, g_weight >= FW_BOLD, &L);
            }
        }
        size->cx = iceil(text_width(&L, (const unsigned char *)g_text, g_len)) + 1;
        size->cy = L.line;
        return TRUE;
    }
    BOOL ok = pExtentW(dc, g_wide, g_wlen, size);
    if (ok && g_wlen && g_text == g_out) {
        /* a translation much longer than the English text would run out of the box made for it: draw it smaller */
        WCHAR en[512];
        int m = MultiByteToWideChar(CP_ACP, 0, s, len < 511 ? len : 511, en, 511);
        SIZE e;
        if (m > 0 && pExtentW(dc, en, m, &e) && e.cx > 0 && size->cx * 100 > e.cx * 112 && g_height) {
            int h = (int)((__int64)g_height * e.cx * 112 / ((__int64)size->cx * 100));
            if (h > -6 && g_height < 0) h = -6;
            HFONT f = make_font(h);
            if (f) {
                SelectObject(dc, f);
                if (g_smaller) DeleteObject(g_smaller);
                g_smaller = f;
                pExtentW(dc, g_wide, g_wlen, size);
            }
        }
    }
    return ok;
}

BOOL WINAPI mp_TextOutA(HDC dc, int x, int y, LPCSTR s, int len)
{
    if (g_ready != 2) return TextOutA(dc, x, y, s, len);
    prepare(s, len);
    struct layout L;
    if (layout_for(g_height < 0 ? -g_height : g_height, g_weight >= FW_BOLD, &L)
        && draw_bitmap_font(dc, x, y - 1, &L, (const unsigned char *)g_text, g_len))
        return TRUE;
    return pTextOutW(dc, x, y, g_wide, g_wlen);
}

#include "fixes.c"   /* non-text fixes: render handles kept on state load, the log folder */
