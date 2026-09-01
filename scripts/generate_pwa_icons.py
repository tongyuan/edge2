#!/usr/bin/env python3
from __future__ import annotations

import struct
import zlib
from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[1] / "app" / "static"
BACKGROUND = (8, 11, 16, 255)
ACCENT = (98, 230, 181, 255)
WHITE = (245, 247, 251, 255)


def chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def pixel(size: int, x: int, y: int) -> tuple[int, int, int, int]:
    unit_x = x / size
    unit_y = y / size
    in_vertical = 0.22 <= unit_x <= 0.34 and 0.26 <= unit_y <= 0.74
    in_top = 0.22 <= unit_x <= 0.78 and 0.26 <= unit_y <= 0.36
    in_middle = 0.22 <= unit_x <= 0.69 and 0.45 <= unit_y <= 0.55
    in_bottom = 0.22 <= unit_x <= 0.78 and 0.64 <= unit_y <= 0.74
    in_dot = ((unit_x - 0.75) ** 2) + ((unit_y - 0.21) ** 2) <= 0.055**2
    if in_dot:
        return WHITE
    if in_vertical or in_top or in_middle or in_bottom:
        return ACCENT
    return BACKGROUND


def render(size: int) -> bytes:
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            row.extend(pixel(size, x, y))
        rows.append(bytes(row))
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"".join(rows), level=9))
        + chunk(b"IEND", b"")
    )


def main() -> int:
    for size in (180, 192, 512):
        destination = STATIC_DIR / f"edge-mrz-icon-{size}.png"
        destination.write_bytes(render(size))
        print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
