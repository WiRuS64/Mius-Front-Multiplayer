"""Which units' status differs between two running battle games, and for how long:
status_probe.py <tools dir> <pid host> <pid joiner> [samples=20] [seconds between=1] [host unit prefix=08]

Same fields as combat_diff.py (soldier +0x228d/+0x228e, vehicle +0xd07..+0xd10 without +0xd0d). For each unit that
differed in any sample it prints in how many samples it differed, whose unit it is (host's or joiner's) and the
values seen. A unit that differs in every sample is stuck (state lost); one that differs now and then is lag.
"""
import collections
import sys
import time

sys.path.insert(0, sys.argv[1])
import combat_diff  # noqa: E402
import peek  # noqa: E402


def main():
    ha, hb = peek.open_proc(int(sys.argv[2])), peek.open_proc(int(sys.argv[3]))
    samples = int(sys.argv[4]) if len(sys.argv) > 4 else 20
    pause = float(sys.argv[5]) if len(sys.argv) > 5 else 1
    prefix = sys.argv[6] if len(sys.argv) > 6 else '08'
    count = collections.Counter()
    seen = collections.defaultdict(set)
    per_sample = []
    for s in range(samples):
        a, b = combat_diff.units(ha), combat_diff.units(hb)
        diff = [n for n in set(a) & set(b) if a[n][0] != b[n][0]]
        per_sample.append(len(diff))
        for n in diff:
            count[n] += 1
            seen[n].add('A %s / B %s' % (a[n][0].hex(), b[n][0].hex()))
        if s + 1 < samples:
            time.sleep(pause)
    print('differing per sample: %s' % ' '.join(map(str, per_sample)))
    stuck = 0
    for n, c in count.most_common():
        owner = 'host' if n.rsplit('_', 1)[1].startswith(prefix) else 'joiner'
        stuck += c == samples
        print('  %-26s %-6s %2d/%d  %s' % (n, owner, c, samples, '; '.join(sorted(seen[n]))[:120]))
    print('units differing in every sample: %d' % stuck)


if __name__ == '__main__':
    main()
