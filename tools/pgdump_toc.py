"""Minimal reader for pg_dump custom-format (-Fc) archives, version 1.14 (PG 12-15).
Prints the table of contents; optionally extracts a table's COPY data."""
import sys, zlib, struct

class R:
    def __init__(self, f):
        self.f = f; self.intSize = 4; self.offSize = 8
    def byte(self):
        b = self.f.read(1)
        if not b: raise EOFError
        return b[0]
    def int(self):
        sign = self.byte()
        v = 0
        for i in range(self.intSize):
            v |= self.byte() << (8*i)
        return -v if sign else v
    def str(self):
        n = self.int()
        if n < 0: return None
        return self.f.read(n).decode('utf-8', 'replace')
    def offset(self):
        flag = self.byte()  # 0 = unknown, 1 = pos not set, 2 = pos set
        v = 0
        for i in range(self.offSize):
            v |= self.byte() << (8*i)
        return flag, v

def read_toc(path):
    f = open(path, 'rb'); r = R(f)
    assert f.read(5) == b'PGDMP'
    vmaj, vmin, vrev = r.byte(), r.byte(), r.byte()
    r.intSize, r.offSize = r.byte(), r.byte()
    fmt = r.byte()
    assert (vmaj, vmin) == (1, 14), f"unsupported archive version {vmaj}.{vmin}"
    compression = r.int()
    sec, mn, hr, mday, mon, year, isdst = [r.int() for _ in range(7)]
    dbname, remote_ver, pg_ver = r.str(), r.str(), r.str()
    hdr = dict(version=f"{vmaj}.{vmin}.{vrev}", compression=compression,
               created=f"{year+1900}-{mon+1:02d}-{mday:02d} {hr:02d}:{mn:02d}:{sec:02d}",
               dbname=dbname, server=remote_ver, pg_dump=pg_ver)
    n = r.int()
    entries = []
    for _ in range(n):
        e = {}
        e['dumpId'] = r.int(); e['hadDumper'] = r.int()
        e['tableoid'] = r.str(); e['oid'] = r.str()
        e['tag'] = r.str(); e['desc'] = r.str(); e['section'] = r.int()
        e['defn'] = r.str(); e['dropStmt'] = r.str(); e['copyStmt'] = r.str()
        e['namespace'] = r.str(); e['tablespace'] = r.str(); e['tableam'] = r.str()
        e['owner'] = r.str(); e['withOids'] = r.str()
        deps = []
        while True:
            d = r.str()
            if d is None: break
            deps.append(d)
        e['deps'] = deps
        e['offsetFlag'], e['offset'] = r.offset()
        entries.append(e)
    return hdr, entries, f, r

def read_data(f, r, entry):
    """Return decompressed COPY text for a TABLE DATA entry."""
    f.seek(entry['offset'])
    blk = r.byte(); dumpid = r.int()
    assert blk == ord('1'), f"expected data block, got {blk!r}"
    assert dumpid == entry['dumpId']
    d = zlib.decompressobj()
    out = []
    while True:
        n = r.int()
        if n == 0: break
        out.append(d.decompress(f.read(n)))
    out.append(d.flush())
    return b''.join(out).decode('utf-8', 'replace')

if __name__ == '__main__':
    path = sys.argv[1]
    hdr, entries, f, r = read_toc(path)
    if len(sys.argv) > 2:
        want = sys.argv[2]
        for e in entries:
            if e['desc'] == 'TABLE DATA' and e['tag'] == want:
                sys.stdout.write(read_data(f, r, e)); break
        else:
            sys.exit(f"no TABLE DATA entry named {want}")
    else:
        print("HEADER:", hdr)
        print(f"{len(entries)} TOC entries")
        from collections import Counter
        print("by desc:", Counter(e['desc'] for e in entries).most_common())
        print("\nTABLES (name | defn snippet):")
        for e in entries:
            if e['desc'] == 'TABLE':
                print(f"  {e['namespace']}.{e['tag']}")
        print("\nTABLE DATA entries:")
        for e in entries:
            if e['desc'] == 'TABLE DATA':
                print(f"  {e['namespace']}.{e['tag']}  offset={e['offset']}")
