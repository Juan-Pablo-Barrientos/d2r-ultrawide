"""DXBC container checksum (the MD5 variant that d3dcompiler writes at bytes 4..20)."""
import math
import struct

S = [7, 12, 17, 22] * 4 + [5, 9, 14, 20] * 4 + [4, 11, 16, 23] * 4 + [6, 10, 15, 21] * 4
K = [int(abs(math.sin(i + 1)) * 2 ** 32) & 0xFFFFFFFF for i in range(64)]


def _transform(state, block):
    x = struct.unpack("<16I", block)
    a, b, c, d = state
    for i in range(64):
        if i < 16:
            f, g = (b & c) | (~b & d), i
        elif i < 32:
            f, g = (d & b) | (~d & c), (5 * i + 1) % 16
        elif i < 48:
            f, g = b ^ c ^ d, (3 * i + 5) % 16
        else:
            f, g = c ^ (b | ~d), (7 * i) % 16
        f = (f + a + K[i] + x[g]) & 0xFFFFFFFF
        a, d, c = d, c, b
        b = (b + ((f << S[i]) | (f >> (32 - S[i])))) & 0xFFFFFFFF
    return [(s + v) & 0xFFFFFFFF for s, v in zip(state, (a, b, c, d))]


def checksum(dxbc):
    data = dxbc[20:]
    state = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476]
    full = len(data) - len(data) % 64
    for o in range(0, full, 64):
        state = _transform(state, data[o:o + 64])
    rest = data[full:]
    bits = (len(data) * 8) & 0xFFFFFFFF
    tail = struct.pack("<I", (bits >> 2) | 1)
    if len(rest) + 1 > 56:
        state = _transform(state, rest + b"\x80" + b"\0" * (63 - len(rest)))
        block = struct.pack("<I", bits) + b"\0" * 56 + tail
    else:
        block = struct.pack("<I", bits) + rest + b"\x80"
        block += b"\0" * (60 - len(block)) + tail
    return struct.pack("<4I", *_transform(state, block))


def find(container):
    """Return (offset, size) of the first DXBC blob inside a D2R shader container."""
    start = container.find(b"DXBC")
    if start < 0:
        raise ValueError("no DXBC blob found")
    return start, struct.unpack_from("<I", container, start + 24)[0]
