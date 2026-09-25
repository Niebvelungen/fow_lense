r"""Extract tables from a pg_dump custom-format (-Fc) archive without PostgreSQL installed.
Handles archives whose data offsets were never recorded (streamed dumps, e.g. Heroku).

usage: python pgdump_extract.py DUMP [--out DIR] [--tables t1,t2,...] [--list]
Writes DIR/schema.sql (all DDL in TOC order) and DIR/<table>.tsv (PostgreSQL COPY text format,
tab-separated, \N = NULL, backslash escapes) for each table.
"""
import sys, zlib, argparse, os
sys.path.insert(0, os.path.dirname(__file__))
from pgdump_toc import read_toc

BLK_DATA, BLK_BLOBS = 1, 3

def scan_blocks(f, r):
    """Yield (dumpId, list_of_compressed_chunks) for every data block, in file order."""
    while True:
        b = f.read(1)
        if not b: return
        t = b[0]
        dumpid = r.int()
        if t == BLK_DATA:
            chunks = []
            while True:
                n = r.int()
                if n == 0: break
                chunks.append(f.read(n))
            yield dumpid, chunks
        elif t == BLK_BLOBS:
            raise NotImplementedError("large-object blocks not supported")
        else:
            raise ValueError(f"unknown block type {t} at {f.tell()}")

def decompress(chunks):
    d = zlib.decompressobj()
    return b''.join(d.decompress(c) for c in chunks) + d.flush()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dump'); ap.add_argument('--out', default='data')
    ap.add_argument('--tables', help='comma-separated table names (default: all)')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    hdr, entries, f, r = read_toc(a.dump)
    byid = {e['dumpId']: e for e in entries}
    if a.list:
        for e in entries:
            if e['desc'] == 'TABLE DATA': print(e['tag'])
        return
    want = set(a.tables.split(',')) if a.tables else None
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'schema.sql'), 'w', encoding='utf-8') as s:
        s.write(f"-- from {a.dump}: db={hdr['dbname']} server={hdr['server']} created={hdr['created']}\n")
        for e in entries:
            if e['defn'] and e['desc'] not in ('TABLE DATA',):
                s.write(f"-- {e['desc']}: {e['tag']}\n{e['defn']}\n")
    counts = {}
    for dumpid, chunks in scan_blocks(f, r):
        e = byid[dumpid]
        if want and e['tag'] not in want: continue
        txt = decompress(chunks)
        path = os.path.join(a.out, e['tag'] + '.tsv')
        cols = e['copyStmt'].split('(',1)[1].rsplit(')',1)[0].replace('"','').replace(' ','') if e['copyStmt'] else ''
        with open(path, 'wb') as o:
            o.write(cols.encode() + b'\n'); o.write(txt)
        counts[e['tag']] = txt.count(b'\n')
    for t, n in counts.items(): print(f"{n:>8}  {t}")

if __name__ == '__main__': main()
