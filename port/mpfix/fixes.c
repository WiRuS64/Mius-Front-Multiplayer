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
