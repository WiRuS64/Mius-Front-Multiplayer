"""Extract original PE files stored in a Ghidra project's FileBytes (masked ChainedBuffer) buffers."""
import sys,struct,hashlib,re
from pathlib import Path
rep=Path(sys.argv[1]); out=Path(sys.argv[2]); out.mkdir(exist_ok=True)
M=bytes.fromhex((Path(__file__).resolve().parent/'mask.hex').read_text())
idx=(rep/'idata'/'~index.dat').read_text()
names=dict(re.findall(r'^\s+(\w{8}):([\w.]+):',idx,re.M))
BS=0x4000
for num,name in sorted(names.items()):
    d=(rep/'idata'/'00'/f'~{num}.db'/'db.1.gbf').read_bytes()
    blocks={}
    for b in range(BS,len(d),BS):
        blk=d[b:b+BS]
        if len(blk)<BS or blk[5]!=0x09: continue
        bid=struct.unpack('>I',blk[1:5])[0]
        blocks[bid]=bytes(blk[j]^M[(j-12)%128] for j in range(6,BS))
    ids=sorted(blocks)
    start=[i for i in ids if blocks[i][:2]==b'MZ']
    if not start: print(name,'no MZ'); continue
    i=start[0]; data=bytearray()
    while i in blocks: data+=blocks[i]; i+=1
    pe=struct.unpack('<I',data[0x3c:0x40])[0]
    ns=struct.unpack('<H',data[pe+6:pe+8])[0]; oh=struct.unpack('<H',data[pe+20:pe+22])[0]
    st=pe+24+oh; end=0
    for k in range(ns):
        raw,ptr=struct.unpack('<II',data[st+40*k+16:st+40*k+24]); end=max(end,raw+ptr)
    ok = end<=len(data)
    data=data[:end]
    (out/name).write_bytes(data)
    ts=struct.unpack('<I',data[pe+8:pe+12])[0]
    print(f'{name:22} start_id={start[0]} len={len(data)} complete={ok} ts={ts:#x} sha256={hashlib.sha256(data).hexdigest()}')
