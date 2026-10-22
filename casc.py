"""Minimal read-only CASC reader for a local D2R install (TVFS root). Standard library only.

usage: py casc.py <game dir> list <substring>
       py casc.py <game dir> get <path> <out file>
"""
import glob
import os
import struct
import sys
import zlib


class Casc:
    def __init__(self, game):
        self.data = os.path.join(game, "Data", "data")
        self.index = {}
        for idx in glob.glob(os.path.join(self.data, "*.idx")):
            self._load_idx(idx)
        build_key = open(os.path.join(game, ".build.info")).read().splitlines()[1].split("|")[2]
        cfg = os.path.join(game, "Data", "config", build_key[:2], build_key[2:4], build_key)
        self.config = {}
        for line in open(cfg):
            if " = " in line:
                k, v = line.strip().split(" = ", 1)
                self.config[k] = v.split()

    def _load_idx(self, path):
        b = open(path, "rb").read()
        hh_size = struct.unpack_from("<I", b, 0)[0]
        ver, bucket, extra, size_len, offs_len, key_len, offs_bits = struct.unpack_from("<HBBBBBB", b, 8)
        assert ver == 7 and size_len == 4 and offs_len == 5 and key_len == 9, (path, ver)
        pos = (8 + hh_size + 15) & ~15
        entries_size = struct.unpack_from("<I", b, pos)[0]
        pos += 8
        entry_len = key_len + offs_len + size_len
        mask = (1 << offs_bits) - 1
        for p in range(pos, pos + entries_size, entry_len):
            key = b[p:p + 9]
            off = int.from_bytes(b[p + 9:p + 14], "big")
            size = struct.unpack_from("<I", b, p + 14)[0]
            self.index.setdefault(key, (off >> offs_bits, off & mask, size))

    def read_ekey(self, ekey):
        archive, off, size = self.index[bytes.fromhex(ekey)[:9] if isinstance(ekey, str) else ekey[:9]]
        with open(os.path.join(self.data, "data.%03d" % archive), "rb") as f:
            f.seek(off)
            raw = f.read(size)
        return blte(raw[30:])


def blte(b):
    assert b[:4] == b"BLTE", b[:4]
    hdr = struct.unpack_from(">I", b, 4)[0]
    if hdr == 0:
        chunks = [(len(b) - 8, None)]
        pos = 8
    else:
        count = int.from_bytes(b[9:12], "big")
        chunks = []
        for i in range(count):
            csize, dsize = struct.unpack_from(">II", b, 12 + i * 24)
            chunks.append((csize, dsize))
        pos = hdr
    out = bytearray()
    for csize, _ in chunks:
        c = b[pos:pos + csize]
        pos += csize
        mode = c[:1]
        if mode == b"N":
            out += c[1:]
        elif mode == b"Z":
            out += zlib.decompress(c[1:])
        else:
            raise ValueError("unsupported BLTE chunk mode %r" % mode)
    return bytes(out)


def tvfs_files(t):
    assert t[:4] == b"TVFS"
    ekey_size = t[6]
    path_off, path_size, vfs_off, vfs_size, cft_off, cft_size = struct.unpack_from(">IIIIII", t, 12)
    cft_len = 1 if cft_size <= 0xFF else 2 if cft_size <= 0xFFFF else 3 if cft_size <= 0xFFFFFF else 4

    def spans(node):
        p = vfs_off + node
        n = t[p]
        p += 1
        out = []
        for _ in range(n):
            c_off, c_len = struct.unpack_from(">II", t, p)
            cft = int.from_bytes(t[p + 8:p + 8 + cft_len], "big")
            p += 8 + cft_len
            e = cft_off + cft
            out.append((t[e:e + ekey_size], c_len))
        return out

    files = {}

    def walk(p, end, prefix):
        base = prefix
        while p < end:
            name = prefix
            if t[p] == 0:
                name += "/"
                p += 1
            if p < end and t[p] != 0xFF:
                n = t[p]
                name += t[p + 1:p + 1 + n].decode("utf-8", "replace")
                p += 1 + n
            if p < end and t[p] == 0:
                name += "/"
                p += 1
            elif p < end and t[p] != 0xFF:
                name += "/"
            if p < end and t[p] == 0xFF:
                val = struct.unpack_from(">I", t, p + 1)[0]
                p += 5
                if val & 0x80000000:
                    sub_end = p + (val & 0x7FFFFFFF) - 4
                    walk(p, sub_end, name)
                    p = sub_end
                else:
                    files[name] = spans(val)
                prefix = base
            else:
                prefix = name
    walk(path_off, path_off + path_size, "")
    return files


def main():
    game, cmd = sys.argv[1], sys.argv[2]
    c = Casc(game)
    files = tvfs_files(c.read_ekey(c.config["vfs-2"][1]))
    if cmd == "list":
        for name in sorted(files):
            if sys.argv[3].lower() in name.lower():
                print(name, sum(s[1] for s in files[name]))
    elif cmd == "get":
        name = sys.argv[3]
        data = b"".join(c.read_ekey(ek) for ek, _ in files[name])
        open(sys.argv[4], "wb").write(data)
        print("wrote", sys.argv[4], len(data), "bytes")


if __name__ == "__main__":
    main()
