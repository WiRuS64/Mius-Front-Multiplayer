/* Mius-Front Multiplayer: fixes that are not about texts. Included at the end of text.c (one object for
   link_coff.py), so the same rules hold: freestanding, no relocations, only the mod's imports.

   1. mp_state_load_keep (replaces keep_handles.asm, 2.2.1): the mod loads the other player's unit states into this
      game's copies of his units (state_load, mod rva 2eca4h, called at 2f092h inside state_load_keep_motion).
      A vehicle's state carries numbers that only mean something in the renderer of the game that wrote it: the
      model node handles at +11a8h..+11b7h (2.2.1), and the turret/gun node handles of its weapon mounts - an
      array of 160h-byte entries at [+18d0h] (count +18dch), two handles at +0a8h / +0ach (-1 = none) that
      adv_physic+40cd8h hands to the renderer every frame. Measured on one PC (qa\turret_probe.py): a handle set
      to -1 in the host's copy of a joiner vehicle is back at the joiner's value 2 s later. Two PCs whose
      renderers number their node groups differently crash there (friend's dump 2026-11-06 14:27:
      basic_render+12ffdh, group 14fh empty, called from adv_physic+41865h). Both blocks are now kept.

   2. mp_log_path (the sprintf_s at mod rva 2757h that names the log file): the logs go to <game>\mp_logs, a
      folder of their own that a player can zip and send, instead of <game>\out among the engine's files.
      Logs there older than 14 days are deleted. If the folder cannot be made the log stays in out. */

int state_load(void *obj, const void *data, size_t size);      /* mod rva 2eca4h, resolved by build_mpfix.py */

#define TECHN_NAME 0x3A6E686365745F69ull   /* "i_techn:" - an object's name starts at +8 */
#define MOUNTS_MAX 32

static unsigned g_kept_logged;

int mp_state_load_keep(char *obj, const void *data, size_t size)
{
    unsigned char model[16];
    int mount[MOUNTS_MAX][2];
    char *arr = 0;
    unsigned n = 0, i;
    int techn = *(unsigned long long *)(obj + 8) == TECHN_NAME;
    if (techn) {
        for (i = 0; i < 16; i++) model[i] = (unsigned char)obj[0x11a8 + i];
        arr = *(char **)(obj + 0x18d0);
        n = *(unsigned *)(obj + 0x18dc);
        if (!arr || n > MOUNTS_MAX) n = 0;
        for (i = 0; i < n; i++) {
            mount[i][0] = *(int *)(arr + 0x160 * i + 0xa8);
            mount[i][1] = *(int *)(arr + 0x160 * i + 0xac);
        }
    }
    int r = state_load(obj, data, size);
    if (techn) {
        for (i = 0; i < 16; i++) obj[0x11a8 + i] = (char)model[i];
        char *now = *(char **)(obj + 0x18d0);
        unsigned m = *(unsigned *)(obj + 0x18dc);
        if (now == arr && m >= n) {
            for (i = 0; i < n; i++) {
                int *h = (int *)(now + 0x160 * i + 0xa8);
                if ((h[0] != mount[i][0] || h[1] != mount[i][1]) && g_kept_logged < 3) {
                    g_kept_logged++;
                    mp_log("state: %.40s: the other game's turret/gun render handles %x/%x kept local as %x/%x",
                           obj + 8, h[0], h[1], mount[i][0], mount[i][1]);
                }
                h[0] = mount[i][0];
                h[1] = mount[i][1];
            }
        }
    }
    return r;
}

/* ------------------------------------------------------------------ the turn must not hang (2.6.0)
   When both players have pressed next turn, the host's game waits for the other game to send its map. The original
   waits without any limit, and the joining game only sends while its map is on screen (controller +1200h == 0 and
   the operation pointer +1d8h set). A joining player who left for the Operations screen (or whose game cannot save)
   never sends; the host's map stays blocked for good. Owner's two-PC game 2026-11-06 14:24: "asking ... for his
   moves", then nothing until the other game closed.

   mp_host_map_frame runs in the host's map frame instead of "call menu_controller_of" at mod rva 11989h, and
   gives up on a collection that does not get anywhere: 8 s after the other player has left the map, 45 s when his
   game has not offered its map, 180 s when the transfer started but did not finish. The turn is not ended; both
   players press next turn again.

   mp_on_screen_asked is "call operation_on_screen" at mod rva 1a734h, where the joining game answers the host's
   request: it says in the log and on screen why the moves cannot be sent. */
extern char g_tactical, g_connected, g_map_collect, g_turn_done, g_peer_on_map, g_map_note[0x78];
extern unsigned g_map_collect_since, g_map_restart_at, g_map_in_hash;
void *menu_controller_of(void *om);         /* mod rva 143f0h */
void *operation_on_screen(void *om);        /* mod rva 17bc8h */

/* The top line of the game; the mod's own branches hide g_map_note in most states of the map, so a note of ours is
   put in place of the part after the last "  -  " for 12 s (the translation works on the whole line when drawn). */
static unsigned long g_note_until;
static char g_status_buf[420];
const char *session_status(void);           /* mod rva 1daa0h */

static void set_note(const char *s)
{
    int i = 0;
    for (; s[i] && i < (int)sizeof g_map_note - 1; i++) g_map_note[i] = s[i];
    g_map_note[i] = 0;
    g_note_until = GetTickCount() + 12000;
}

/* find_local_ip asks which address the default route uses. With Cloudflare WARP or a similar tunnel (198.18.0.0/15, a
   range reserved for benchmarks and used by such tools) that is the tunnel's own address: nobody can reach it, and the
   lobby and the UPnP mapping used it (seen on the owner's PC: "hosting battle on 198.18.0.1"). Then the address of a
   working network adapter with a gateway is used instead, a private LAN address first. */
const char *inet_ntop(int af, const void *src, char *buf, size_t n);
void *malloc(size_t n);
void free(void *p);

const char *mp_local_ip(int af, const void *src, char *buf, size_t n)
{
    typedef HMODULE (WINAPI *load_t)(const char *);
    typedef unsigned long (WINAPI *gaa_t)(unsigned long, unsigned long, void *, void *, unsigned long *);
    const char *r = inet_ntop(af, src, buf, n);
    const unsigned char *a = (const unsigned char *)src;
    load_t load;
    HMODULE lib;
    gaa_t gaa;
    unsigned long len = 0x10000, best = 0xffffffff;
    unsigned char ip[4];
    char *list, *p, *u;
    if (af != 2 || !r || a[0] != 198 || (a[1] & 0xfe) != 18) return r;
    load = (load_t)GetProcAddress(GetModuleHandleA("kernel32.dll"), "LoadLibraryA");
    lib = load ? load("iphlpapi.dll") : 0;
    gaa = lib ? (gaa_t)GetProcAddress(lib, "GetAdaptersAddresses") : 0;
    list = gaa ? (char *)malloc(len) : 0;
    if (!list) return r;
    /* IP_ADAPTER_ADDRESSES (x64): +8 next, +24 first unicast, +100 type, +104 status, +208 first gateway, +216 metric;
       flags: no anycast, multicast or DNS lists, with gateways */
    if (gaa(2, 0x8e, 0, list, &len) == 0) {
        for (p = list; p; p = *(char **)(p + 8)) {
            unsigned type = *(unsigned *)(p + 100);
            if (*(unsigned *)(p + 104) != 1 || !*(void **)(p + 208) || type == 24 || type == 131) continue;
            for (u = *(char **)(p + 24); u; u = *(char **)(u + 8)) {
                const unsigned char *sa = *(const unsigned char **)(u + 16), *q = sa + 4;
                unsigned long score = *(unsigned *)(p + 216);
                int lan = q[0] == 10 || (q[0] == 192 && q[1] == 168) || (q[0] == 172 && (q[1] & 0xf0) == 16);
                if (sa[0] != 2 || (q[0] == 198 && (q[1] & 0xfe) == 18) || (q[0] == 169 && q[1] == 254) || q[0] == 127) continue;
                if (!lan) score += 0x10000000ul;
                if (score < best) { best = score; ip[0] = q[0]; ip[1] = q[1]; ip[2] = q[2]; ip[3] = q[3]; }
            }
        }
    }
    free(list);
    if (best != 0xffffffff) {
        char tunnel[64];
        int i = 0;
        for (; buf[i] && i < 63; i++) tunnel[i] = buf[i];
        tunnel[i] = 0;
        r = inet_ntop(2, ip, buf, n);
        mp_log("net: the default route goes through a tunnel (%s); this PC's address on its network is %s", tunnel, buf);
    }
    return r;
}

/* ------------------------------------------------------------------ the other game's numbers must arrive (2.6.1)
   Each game sends the other a table of what its description and object numbers stand for. Until a game has the
   other's table it holds every hit received (mod rva 3ce10h) and loads no state (1c630h). In the owners' two-PC
   battle of 2026-11-09 the joining game had the host's table only after the battle: 44434 hits on the host's units
   were never carried out there, so those soldiers stayed alive in that game. Why the first table did not complete
   is not known; the table sent after the battle arrived in 2.4 s.

   mp_numbers_due replaces xlate_frame's look at "send due" (398e8h, after its 3 s limit): a game still missing the
   other's table 6 s after its connection began asks for it, every 6 s. The request is a table record of kind 4 with
   no entries and a marker. mp_numbers_received replaces the call of xlate_received (3506ch): it takes the request
   out, marks this game's tables as due, and says in the log when a table starts to arrive. */
extern char g_xlate_ready, g_xlate_due;
extern unsigned g_expect_desc, g_expect_obj;
extern char *g_their_desc[2], *g_their_obj[2];     /* std::vector begin, end: entries of 8 bytes */
void xlate_received(const char *rec, void *om);     /* mod rva 39a40h */
void shots_queue(char *rec);                        /* mod rva 34c74h: takes a copy, sets its sequence number */

#define NUMBERS_ASK 0x4e53524du         /* marker at +54h of the request */
#define NUMBERS_WAIT 6000ul
static unsigned long g_numbers_t0, g_numbers_asked, g_numbers_drop_until;
static unsigned g_numbers_recs, g_numbers_asks;
static int g_numbers_drop = -1, g_numbers_no_ask = -1;

static int env_number(const char *name)
{
    char v[16];
    int i = 0, n = 0;
    if (!GetEnvironmentVariableA(name, v, sizeof v)) return 0;
    for (; v[i] >= '0' && v[i] <= '9'; i++) n = n * 10 + (v[i] - '0');
    return n ? n : 1;
}

int mp_numbers_due(void)
{
    unsigned long now = GetTickCount();
    char rec[0xdc];
    int i;
    if (g_xlate_due) { g_numbers_t0 = g_numbers_asked = now; return 1; }
    if (g_xlate_ready || !g_numbers_t0 || now - g_numbers_t0 < NUMBERS_WAIT || now - g_numbers_asked < NUMBERS_WAIT) return 0;
    if (g_numbers_no_ask < 0) g_numbers_no_ask = env_number("MP_TEST_NO_NUMBERS_ASK");   /* the test with the fix off */
    if (g_numbers_no_ask) return 0;
    g_numbers_asked = now;
    g_numbers_asks++;
    if (g_numbers_asks <= 20)
        mp_log("numbers: the other game's numbers are not here %lu s after connecting (%u of %u descriptions, %u of %u objects, %u records came) - asking again",
               (now - g_numbers_t0) / 1000, (unsigned)((g_their_desc[1] - g_their_desc[0]) / 8), g_expect_desc,
               (unsigned)((g_their_obj[1] - g_their_obj[0]) / 8), g_expect_obj, g_numbers_recs);
    for (i = 0; i < (int)sizeof rec; i++) rec[i] = 0;
    rec[4] = 4;
    *(unsigned *)(rec + 0x54) = NUMBERS_ASK;
    shots_queue(rec);
    return 0;
}

void mp_numbers_received(const char *rec, void *om)
{
    unsigned long now = GetTickCount();
    if (rec[4] == 4 && *(const unsigned *)(rec + 0x4c) == 0 && *(const unsigned *)(rec + 0x54) == NUMBERS_ASK) {
        mp_log("numbers: the other game asks for this game's numbers again");
        g_xlate_due = 1;
        return;
    }
    if (g_numbers_drop < 0) g_numbers_drop = env_number("MP_TEST_DROP_NUMBERS");     /* test: milliseconds of tables lost */
    if (g_numbers_drop) {
        if (!g_numbers_drop_until) g_numbers_drop_until = now + g_numbers_drop;
        if ((long)(now - g_numbers_drop_until) < 0) return;
    }
    if (!g_numbers_recs++) mp_log("numbers: the other game's numbers begin to arrive (%u entries)", *(const unsigned *)(rec + 0x4c));
    xlate_received(rec, om);
}

/* ------------------------------------------------------------------ unit states across different renderer numbering (2.6.1)
   A unit state carries renderer node handles: group << 10 | node. The group is the model's place in the renderer's
   tables (all soldiers share one, each vehicle model has its own), the node is the place inside the model. Two games
   that load the models in another order give the same model another group, so another game's state names groups
   that are something else here. The mod's guard (handles_match, mod rva 2e7e0h, called at 31a13h) then refused the
   state and the unit was followed by position only: in the owners' battle of 2026-11-09 about 5400 of every 5400
   states. (6 groups at most; it already worked out whether the groups could be matched, but only kept that.)

   mp_handles_ok replaces that call. A state whose part list matches exactly is loaded as before. Otherwise, when the
   part counts are the same, every part's node is the same and the groups match one to one, every value in the state
   that names one of the other game's groups is given this game's group, and the state is loaded. Anything else is
   refused as before. The part handles themselves are put back by the mod's own guard after the load.

   Test: MP_TEST_SHIFT_GROUPS=<n> moves every group of this game's units by n in each state received, as if another
   PC had numbered them; MP_TEST_NO_GROUP_MAP=1 switches the matching off; MP_TEST_GROUPS_UNTRANSLATED=1 loads such states
   without renumbering (to show that the test sees the other game's groups left in a unit). */
unsigned char handles_match(void *o, const unsigned char *d, size_t size);   /* mod rva 2e7e0h; the answer is in al only */

#define GROUPS_MAX 8
static unsigned long long g_grp_units, g_grp_values, g_grp_refused, g_grp_test_moved;
static unsigned long g_grp_report;
static unsigned g_grp_logged;
static int g_grp_shift = -1, g_grp_off = -1, g_grp_raw;

static unsigned rd32(const unsigned char *p) { return p[0] | p[1] << 8 | p[2] << 16 | (unsigned)p[3] << 24; }
static void wr32(unsigned char *p, unsigned v) { p[0] = (unsigned char)v; p[1] = (unsigned char)(v >> 8); p[2] = (unsigned char)(v >> 16); p[3] = (unsigned char)(v >> 24); }

/* the part list of a saved unit: after 296h fixed bytes, counted lists {u32 capacity, u32 count, records} of 11h, 8,
   (8 bytes), 4, 40h and 4ch bytes; a part record holds its node handle at +40h */
static unsigned char *blob_parts(unsigned char *d, size_t size, unsigned *count)
{
    static const unsigned rec[] = { 0x11, 8, 0, 4, 0x40, 0x4c };
    size_t pos = 0x296, at = 0;
    unsigned i, n = 0;
    for (i = 0; i < 6; i++) {
        if (!rec[i]) { pos += 8; continue; }
        if (pos + 8 > size) return 0;
        n = rd32(d + pos + 4);
        pos += 8;
        if (n > 0x10000 || pos + (size_t)n * rec[i] > size) return 0;
        at = pos;
        pos += (size_t)n * rec[i];
    }
    *count = n;
    return d + at;
}

/* every value in the state naming group from[j] is given group to[j] (the state is packed: any byte offset) */
static unsigned retarget(unsigned char *d, size_t size, const unsigned *from, const unsigned *to, unsigned k)
{
    unsigned changed = 0, j;
    size_t i = 0;
    while (i + 4 <= size) {
        unsigned v = rd32(d + i), g = v >> 10;
        for (j = 0; j < k && from[j] != g; j++) {}
        if (j < k && v != 0xffffffffu) {
            wr32(d + i, to[j] << 10 | (v & 0x3ff));
            changed++;
            i += 4;
        } else {
            i++;
        }
    }
    return changed;
}

/* MP_TEST_DUMP_STATES=<n>: the first n states received are written to mp_state_dump.bin in the game's folder:
   per state u32 size, u32 part count, 48 bytes of the unit's name, this game's part node handles, the state */
typedef void *(__stdcall *CreateFileA_f)(const char *, unsigned long, unsigned long, void *, unsigned long, unsigned long, void *);
typedef int (__stdcall *WriteFile_f)(void *, const void *, unsigned long, unsigned long *, void *);
static int g_dump_left = -1;
static void *g_dump_file;
static WriteFile_f g_write;
static void dump_state(char *o, const unsigned char *d, size_t size, char *parts, unsigned n)
{
    unsigned hd[14], i, h;
    unsigned long w;
    if (g_dump_left < 0) {
        CreateFileA_f cf;
        void *k32 = GetModuleHandleA("kernel32.dll");
        g_dump_left = env_number("MP_TEST_DUMP_STATES");
        if (!g_dump_left) return;
        cf = (CreateFileA_f)GetProcAddress(k32, "CreateFileA");
        g_write = (WriteFile_f)GetProcAddress(k32, "WriteFile");
        g_dump_file = cf && g_write ? cf("mp_state_dump.bin", 0x40000000ul, 1, 0, 2, 0x80, 0) : 0;
        if (g_dump_file == (void *)-1) g_dump_file = 0;
        mp_log("state: test: %d states go to mp_state_dump.bin%s", g_dump_left, g_dump_file ? "" : " - could NOT be opened");
    }
    if (!g_dump_left || !g_dump_file || !parts || n >= 4096) return;
    g_dump_left--;
    hd[0] = (unsigned)size;
    hd[1] = n;
    for (i = 0; i < 48; i++) ((char *)(hd + 2))[i] = o[8 + i];
    g_write(g_dump_file, hd, sizeof hd, &w, 0);
    for (i = 0; i < n; i++) { h = *(unsigned *)(parts + i * 0x60 + 0x48); g_write(g_dump_file, &h, 4, &w, 0); }
    g_write(g_dump_file, d, (unsigned long)size, &w, 0);
}

int mp_handles_ok(char *o, unsigned char *d, size_t size)
{
    unsigned from[GROUPS_MAX], to[GROUPS_MAX], all_t[GROUPS_MAX * 2], all_m[GROUPS_MAX * 2];
    unsigned k = 0, na = 0, n = *(unsigned *)(o + 0x85c), bn = 0, i, j, moved;
    char *parts = *(char **)(o + 0x850);
    unsigned char *bp;
    unsigned long now = GetTickCount();
    if (g_grp_shift < 0) { g_grp_shift = env_number("MP_TEST_SHIFT_GROUPS"); g_grp_off = env_number("MP_TEST_NO_GROUP_MAP"); g_grp_raw = env_number("MP_TEST_GROUPS_UNTRANSLATED"); }
    if (g_dump_left) dump_state(o, d, size, parts, n);
    if (g_grp_shift && parts && n && n < 4096) {
        /* test: this unit's groups as another PC would have numbered them */
        for (i = 0; i < n; i++) {
            unsigned g = *(unsigned *)(parts + i * 0x60 + 0x48) >> 10;
            if (*(unsigned *)(parts + i * 0x60 + 0x48) == 0xffffffffu || g < 0x10) continue;
            for (j = 0; j < k && from[j] != g; j++) {}
            if (j == k && k < GROUPS_MAX) { from[k] = g; to[k] = g + (unsigned)g_grp_shift; k++; }
        }
        g_grp_test_moved += retarget(d, size, from, to, k);
        k = 0;
    }
    if (handles_match(o, d, size)) return 1;
    bp = g_grp_off ? 0 : blob_parts(d, size, &bn);
    if (!bp || !parts || bn != n || !n || n >= 4096) { g_grp_refused++; return 0; }
    for (i = 0; i < n; i++) {
        unsigned t = rd32(bp + i * 0x4c + 0x40), m = *(unsigned *)(parts + i * 0x60 + 0x48);
        if (t == 0xffffffffu || m == 0xffffffffu) { if (t != m) { g_grp_refused++; return 0; } continue; }
        if ((t & 0x3ff) != (m & 0x3ff) || (t >> 10) < 0x10 || (m >> 10) < 0x10) { g_grp_refused++; return 0; }
        for (j = 0; j < na && all_t[j] != t >> 10 && all_m[j] != m >> 10; j++) {}
        if (j < na) {
            if (all_t[j] != t >> 10 || all_m[j] != m >> 10) { g_grp_refused++; return 0; }   /* not one to one */
            continue;
        }
        if (na == GROUPS_MAX * 2) { g_grp_refused++; return 0; }
        all_t[na] = t >> 10;
        all_m[na] = m >> 10;
        na++;
        if (t >> 10 != m >> 10) {
            if (k == GROUPS_MAX) { g_grp_refused++; return 0; }
            from[k] = t >> 10;
            to[k] = m >> 10;
            k++;
        }
    }
    moved = g_grp_raw ? 0 : retarget(d, size, from, to, k);   /* the test of the test: loaded as the other game numbered it */
    g_grp_units++;
    g_grp_values += moved;
    if (g_grp_logged < 3) {
        g_grp_logged++;
        mp_log("state: %.40s: the other game numbers its %u model group(s) differently (first %x here %x) - %u values renumbered, state loaded",
               o + 8, k, k ? from[0] : 0, k ? to[0] : 0, moved);
    }
    if (now - g_grp_report >= 30000) {
        g_grp_report = now;
        mp_log("state: so far %llu states loaded with the other game's model groups renumbered (%llu values), %llu refused%s",
               g_grp_units, g_grp_values, g_grp_refused, g_grp_shift ? " [test: groups moved]" : "");
    }
    return 1;
}

/* the host's game retries the sharing every 15 s while a battle of this turn is pending; until now only the log said so */
void mp_no_share_log(const char *fmt)
{
    mp_log(fmt);
    set_note("this turn's battles are not over yet - the map is shared when they are");
    g_note_until = GetTickCount() + 17000;
}

const char *mp_session_status(void)
{
    const char *line = session_status();
    if (g_note_until && (long)(GetTickCount() - g_note_until) < 0 && g_map_note[0]) {
        int n = 0, cut = -1, k = 0;
        for (; line[n]; n++)
            if (line[n] == ' ' && line[n + 1] == ' ' && line[n + 2] == '-' && line[n + 3] == ' ' && line[n + 4] == ' ') cut = n;
        if (cut < 0 || cut > 300) return line;
        for (n = 0; n < cut + 5; n++) g_status_buf[n] = line[n];
        for (; g_map_note[k] && n < (int)sizeof g_status_buf - 1; k++) g_status_buf[n++] = g_map_note[k];
        g_status_buf[n] = 0;
        return g_status_buf;
    }
    return line;
}

void *mp_host_map_frame(void *om)
{
    if (g_map_collect && !g_map_restart_at) {
        unsigned long waited = GetTickCount() - g_map_collect_since;
        unsigned long limit = !g_peer_on_map ? 8000ul : g_map_in_hash ? 180000ul : 45000ul;
        if (waited > limit) {
            mp_log("map: the other player's moves did not arrive in %lu s (%s); the turn is not ended, press next turn again",
                   waited / 1000, !g_peer_on_map ? "he has left the map" : g_map_in_hash ? "the transfer did not finish" : "his game did not offer its map");
            g_map_collect = 0;
            g_turn_done = 0;
            g_map_in_hash = 0;
            set_note("the other player's moves did not arrive - press next turn again");
        }
    }
    return menu_controller_of(om);
}

void *mp_on_screen_asked(void *om)
{
    static unsigned long last;
    void *op = operation_on_screen(om);
    if (!op) {
        unsigned long now = GetTickCount();
        if (now - last > 5000) {
            char *c = (char *)menu_controller_of(om);
            last = now;
            mp_log("map: the host asks for this player's moves, but the map is not on screen (controller %p, screen %d, mode %d, operation %p)",
                   c, c ? *(int *)(c + 0x1258) : -1, c ? *(int *)(c + 0x1200) : -1, c ? *(void **)(c + 0x1d8) : 0);
            set_note("the host is waiting for your moves - go back to the map");
        }
    }
    return op;
}

/* ------------------------------------------------------------------ log folder */
static int put_s(char *d, int at, int cap, const char *s)
{
    while (*s && at < cap - 1) d[at++] = *s++;
    d[at] = 0;
    return *s ? -1 : at;
}

static void prune_logs(const char *dir)
{
    char pat[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAA fd;
    FILETIME now;
    ULARGE_INTEGER t, w;
    int k = put_s(pat, 0, MAX_PATH, dir);
    if (k < 0 || put_s(pat, k, MAX_PATH, "\\basic_network_*.log") < 0) return;
    GetSystemTimeAsFileTime(&now);
    t.LowPart = now.dwLowDateTime; t.HighPart = now.dwHighDateTime;
    HANDLE h = FindFirstFileA(pat, &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        w.LowPart = fd.ftLastWriteTime.dwLowDateTime; w.HighPart = fd.ftLastWriteTime.dwHighDateTime;
        if (w.QuadPart > t.QuadPart || t.QuadPart - w.QuadPart < 14ull * 24 * 3600 * 10000000ull) continue;
        k = put_s(path, 0, MAX_PATH, dir);
        if (k >= 0 && put_s(path, k, MAX_PATH, "\\") >= 0 && put_s(path, k + 1, MAX_PATH, fd.cFileName) >= 0)
            DeleteFileA(path);
    } while (FindNextFileA(h, &fd));
    FindClose(h);
}

/* called instead of sprintf_s(path, "%s\\basic_network_%s_%lu.log", g_out_dir, g_program, pid); path is
   char[MAX_PATH] */
int mp_log_path(char *buf, const char *fmt, const char *out_dir, const char *program, unsigned long pid)
{
    char dir[MAX_PATH], num[16];
    int k, i = 0;
    (void)fmt;
    k = put_s(dir, 0, MAX_PATH, out_dir);
    while (k > 0 && dir[k - 1] != '\\') k--;            /* <game>\out -> <game>\ */
    if (k > 0) k = put_s(dir, k, MAX_PATH, "mp_logs");
    if (k > 0 && !CreateDirectoryA(dir, 0) && GetLastError() != ERROR_ALREADY_EXISTS) k = -1;
    if (k < 0) put_s(dir, 0, MAX_PATH, out_dir);
    else prune_logs(dir);
    do { num[i++] = (char)('0' + pid % 10); pid /= 10; } while (pid && i < 15);
    char rev[16];
    for (int j = 0; j < i; j++) rev[j] = num[i - 1 - j];
    rev[i] = 0;
    k = put_s(buf, 0, MAX_PATH, dir);
    if (k >= 0) k = put_s(buf, k, MAX_PATH, "\\basic_network_");
    if (k >= 0) k = put_s(buf, k, MAX_PATH, program);
    if (k >= 0) k = put_s(buf, k, MAX_PATH, "_");
    if (k >= 0) k = put_s(buf, k, MAX_PATH, rev);
    if (k >= 0) k = put_s(buf, k, MAX_PATH, ".log");
    return k;
}
