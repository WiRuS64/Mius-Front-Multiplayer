"""Port mpmod1 release 2 (basic_network.codelib) to another compile of Graviteam Tactics: Mius-Front build 3598.

  python -I apply_patch.py <spec.json> <input basic_network.codelib> <output path>

spec.json:
  { "input_sha256": "...",              # the exact release-2 file this spec was written for
    "target": "Steam public, buildid 15814271",
    "edits": [ { "file_offset": "0x18c3d", "expect": "60 66 0d 00", "write": "80 60 0d 00", "why": "adv_opgame op save" }, ... ] }

Rules (playbook/patching-a-closed-mod-exe.md): refuses any input whose SHA-256 is not input_sha256, never writes to its
input (output must be a different path), checks every overwritten byte range against "expect" first and stops on the
first mismatch, and prints the SHA-256 of the output so anyone can confirm they made the same file.
"""
import hashlib
import json
import sys
from pathlib import Path


def hx(s):
    return bytes.fromhex(s.replace(" ", ""))


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    spec = json.loads(Path(sys.argv[1]).read_text())
    src, dst = Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()
    if src == dst:
        print("refused: the output path is the input path")
        return 1
    data = bytearray(src.read_bytes())
    have = hashlib.sha256(data).hexdigest()
    if have != spec["input_sha256"].lower():
        print(f"refused: {src.name} has SHA-256 {have}, this patch is for {spec['input_sha256']}")
        return 1
    seen = set()
    for e in spec["edits"]:
        off = int(e["file_offset"], 16)
        exp, new = hx(e["expect"]), hx(e["write"])
        if len(exp) != len(new):
            print(f"bad spec at {off:#x}: expect and write differ in length")
            return 1
        span = set(range(off, off + len(new)))
        if span & seen:
            print(f"bad spec at {off:#x}: overlaps an earlier edit")
            return 1
        seen |= span
        if bytes(data[off:off + len(exp)]) != exp:
            print(f"refused at {off:#x} ({e.get('why', '')}): found {data[off:off + len(exp)].hex(' ')}, expected {exp.hex(' ')}")
            return 1
        data[off:off + len(new)] = new
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    print(f"{len(spec['edits'])} edits applied for {spec.get('target', '?')}")
    print(f"output {dst} SHA-256 {hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
