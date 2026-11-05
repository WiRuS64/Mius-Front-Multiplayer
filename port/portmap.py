"""Map RVAs from the build mpmod1 was written for (old_build/, extracted from the author's Ghidra project and checked
against the author's game_build_3598.sha256) to the installed build (game_test/).  Read-only.

  python -I portmap.py <module> <rva> [<rva> ...]      map each rva, print method and evidence
  python -I portmap.py --stats <module>                 how many functions match

Method
  code:  every .pdata range of both builds is disassembled and normalised (rip-relative displacements and rel32/rel8
         branch targets masked, everything else - opcodes, registers, struct offsets, immediates - kept).
         Ranges with a unique identical normalised body are anchors; the rest are paired by order between anchors and
         aligned with difflib.  An rva maps only if its instruction lies in an equal run of the alignment.
         status "exact" = whole function identical, "aligned" = function changed but this instruction's run is equal.
  data:  every old rip-relative reference to [rva-0x200, rva+0x200] whose instruction maps (exact/aligned) votes for
         new_target + (rva - old_target).  status "data k/n" = k of n votes agree.
"""
import bisect
import collections
import difflib
import functools
import hashlib
import struct
import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "old_build"
NEW = HERE.parent / "game_test" / "bin" / "rel" / "x64"


class Mod:
    def __init__(self, path):
        self.pe = pefile.PE(str(path))
        self.img = self.pe.get_memory_mapped_image()
        self.secs = [(s.Name.rstrip(b"\0").decode(), s.VirtualAddress, max(s.Misc_VirtualSize, s.SizeOfRawData))
                     for s in self.pe.sections]
        self.funcs = sorted({(r.struct.BeginAddress, r.struct.EndAddress)
                             for r in getattr(self.pe, "DIRECTORY_ENTRY_EXCEPTION", [])})
        self.starts = [b for b, _ in self.funcs]
        self._dis = {}
        self.md = Cs(CS_ARCH_X86, CS_MODE_64)
        self.md.detail = True

    def section(self, rva):
        for n, va, sz in self.secs:
            if va <= rva < va + sz:
                return n
        return None

    def func_index(self, rva):
        i = bisect.bisect_right(self.starts, rva) - 1
        if i >= 0 and self.funcs[i][0] <= rva < self.funcs[i][1]:
            return i
        return None

    def dis(self, i):
        """[(addr, size, norm, rip_target_or_None)] for function range i"""
        if i in self._dis:
            return self._dis[i]
        b, e = self.funcs[i]
        out = []
        for ins in self.md.disasm(self.img[b:e], b):
            raw = bytearray(ins.bytes)
            tgt = None
            for op in ins.operands:
                if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                    tgt = ins.address + ins.size + op.mem.disp
                    if ins.disp_size:
                        raw[ins.disp_offset:ins.disp_offset + ins.disp_size] = b"\xee" * ins.disp_size
            if ins.group(1) or ins.group(2) or ins.group(7):  # jump, call, branch_relative
                if ins.operands and ins.operands[0].type == X86_OP_IMM and ins.imm_size:
                    raw[ins.imm_offset:ins.imm_offset + ins.imm_size] = b"\xbb" * ins.imm_size
                    tgt = ins.operands[0].imm
                    if ins.imm_size == 1:  # short vs near jumps may swap when code moves
                        raw = bytearray(ins.mnemonic.encode()) + b"\xbb"
                    elif ins.mnemonic.startswith("j"):
                        raw = bytearray(ins.mnemonic.encode()) + b"\xbb"
            out.append((ins.address, ins.size, bytes(raw), tgt))
        self._dis[i] = out
        return out

    def key(self, i):
        return hashlib.sha1(b"|".join(n for _, _, n, _ in self.dis(i))).digest()


@functools.lru_cache(None)
def mods(name):
    return Mod(OLD / f"{name}.codelib"), Mod(NEW / f"{name}.codelib")


@functools.lru_cache(None)
def pairing(name):
    """old func index -> (new func index, 'exact'|'paired')"""
    o, n = mods(name)
    ok = collections.defaultdict(list)
    nk = collections.defaultdict(list)
    for i in range(len(o.funcs)):
        ok[o.key(i)].append(i)
    for j in range(len(n.funcs)):
        nk[n.key(j)].append(j)
    pair = {}
    for k, ol in ok.items():
        nl = nk.get(k, [])
        if len(ol) == 1 and len(nl) == 1:
            pair[ol[0]] = (nl[0], "exact")
    # pair the gaps between anchors by order
    anchors = sorted(pair.items())
    prev_o, prev_n = -1, -1
    for oi, (nj, _) in anchors + [(len(o.funcs), (len(n.funcs), None))]:
        go = list(range(prev_o + 1, oi))
        gn = list(range(prev_n + 1, nj))
        if go and gn:
            if len(go) == len(gn):
                for a, b in zip(go, gn):
                    pair[a] = (b, "paired")
            else:  # greedy by body similarity, keeping order
                sm = difflib.SequenceMatcher(None, [o.key(a) for a in go], [n.key(b) for b in gn], autojunk=False)
                for blk in sm.get_matching_blocks():
                    for t in range(blk.size):
                        pair[go[blk.a + t]] = (gn[blk.b + t], "exact")
                for a in go:
                    if a in pair:
                        continue
                    best = None
                    for b in gn:
                        r = difflib.SequenceMatcher(None, [x[2] for x in o.dis(a)], [x[2] for x in n.dis(b)],
                                                    autojunk=False).quick_ratio()
                        if r > 0.85 and (best is None or r > best[0]):
                            best = (r, b)
                    if best:
                        pair[a] = (best[1], f"similar {best[0]:.2f}")
        prev_o, prev_n = oi, nj
    return pair


def map_code(name, rva):
    o, n = mods(name)
    i = o.func_index(rva)
    if i is None:
        return None, "not in a function"
    p = pairing(name).get(i)
    if not p:
        return None, f"old func {o.funcs[i][0]:#x} has no partner"
    j, how = p
    od, nd = o.dis(i), n.dis(j)
    if how == "exact":
        return n.funcs[j][0] + (rva - o.funcs[i][0]), f"exact (func {o.funcs[i][0]:#x}->{n.funcs[j][0]:#x})"
    sm = difflib.SequenceMatcher(None, [x[2] for x in od], [x[2] for x in nd], autojunk=False)
    idx = next((k for k, x in enumerate(od) if x[0] <= rva < x[0] + x[1]), None)
    if idx is None:
        return None, "rva not on an instruction boundary"
    for a, b, size in sm.get_matching_blocks():
        if a <= idx < a + size:
            ins_o, ins_n = od[idx], nd[b + idx - a]
            ctx = min(idx - a, a + size - 1 - idx)
            return ins_n[0] + (rva - ins_o[0]), (f"aligned/{how} (func {o.funcs[i][0]:#x}->{n.funcs[j][0]:#x}, "
                                                 f"ratio {sm.ratio():.2f}, run {size}, ctx {ctx})")
    return None, f"instruction changed (func {o.funcs[i][0]:#x}->{n.funcs[j][0]:#x}, ratio {sm.ratio():.2f})"


@functools.lru_cache(None)
def rip_refs(name):
    """old build: list of (target, ins_addr) for every rip-relative operand"""
    o, _ = mods(name)
    out = []
    for i in range(len(o.funcs)):
        for a, s, nrm, t in o.dis(i):
            if t is not None:
                out.append((t, a))
    out.sort()
    return out


def map_data(name, rva, window=0x200):
    o, n = mods(name)
    refs = rip_refs(name)
    lo = bisect.bisect_left(refs, (rva - window, -1))
    hi = bisect.bisect_right(refs, (rva + window, 1 << 62))
    votes = collections.Counter()
    for t, a in refs[lo:hi]:
        na, why = map_code(name, a)
        if na is None:
            continue
        j = n.func_index(na)
        nt = next((x[3] for x in n.dis(j) if x[0] == na), None) if j is not None else None
        if nt is None:
            continue
        votes[nt + (rva - t)] += 1 + (t == rva) * 4  # exact references weigh more
    if not votes:
        return None, "no mappable references"
    (best, k), total = votes.most_common(1)[0], sum(votes.values())
    return best, f"data {k}/{total} votes" + ("" if k == total else f" others {dict(votes.most_common(4))}")


def map_any(name, rva):
    o, n = mods(name)
    sec = o.section(rva)
    if sec == ".text":
        r = map_code(name, rva)
        if r[0] is not None or o.func_index(rva) is not None:
            return (sec,) + r
    return (sec,) + map_data(name, rva)


def main():
    a = sys.argv[1:]
    if a and a[0] == "--stats":
        name = a[1]
        o, n = mods(name)
        p = pairing(name)
        c = collections.Counter(h.split()[0] for _, h in p.values())
        print(f"{name}: old {len(o.funcs)} ranges, new {len(n.funcs)}; paired {len(p)}: {dict(c)}")
        return
    name = a[0]
    for x in a[1:]:
        rva = int(x, 16)
        sec, new, why = map_any(name, rva)
        print(f"{name} {rva:#x} [{sec}] -> {('%#x' % new) if new is not None else 'UNMAPPED'}  {why}")


if __name__ == "__main__":
    main()
