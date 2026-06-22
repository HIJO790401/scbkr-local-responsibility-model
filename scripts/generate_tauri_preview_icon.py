"""Generate the P14-C unsigned placeholder Windows icon at build time.

This script intentionally uses only the Python standard library and does not
embed any trademarked or copyrighted logo asset. The generated icon is a simple
preview placeholder used so Tauri can continue Windows preview packaging without
committing a binary .ico file to git.
"""

from __future__ import annotations

import struct
from pathlib import Path

ICON_PATH = Path("apps/desktop/src-tauri/icons/icon.ico")
ICON_SIZE = 32
ICO_HEADER = b"\x00\x00\x01\x00"


def _bgra_pixel(x: int, y: int) -> bytes:
    """Return one opaque BGRA pixel for a simple generated placeholder."""
    border = x in (0, ICON_SIZE - 1) or y in (0, ICON_SIZE - 1)
    diagonal = x == y or x == ICON_SIZE - 1 - y
    badge = 9 <= x <= 22 and 9 <= y <= 22

    if border:
        red, green, blue = 25, 44, 83
    elif diagonal:
        red, green, blue = 245, 158, 11
    elif badge:
        red, green, blue = 30, 64, 175
    else:
        red = 14 + (x * 3)
        green = 116 + (y * 2)
        blue = 144

    return struct.pack("BBBB", blue, green, red, 255)


def build_ico() -> bytes:
    """Build a valid single-image 32-bit Windows ICO file."""
    # ICO BMP payloads store rows bottom-up. For 32-bit icons each row is already
    # 4-byte aligned. The BITMAPINFOHEADER height is doubled because it includes
    # the XOR bitmap plus the 1-bit transparency mask.
    xor_bitmap = b"".join(
        _bgra_pixel(x, y)
        for y in reversed(range(ICON_SIZE))
        for x in range(ICON_SIZE)
    )
    and_mask_stride = ((ICON_SIZE + 31) // 32) * 4
    and_mask = b"\x00" * (and_mask_stride * ICON_SIZE)

    bitmap_info_header = struct.pack(
        "<IIIHHIIIIII",
        40,  # BITMAPINFOHEADER size
        ICON_SIZE,
        ICON_SIZE * 2,
        1,  # planes
        32,  # bits per pixel
        0,  # BI_RGB
        len(xor_bitmap) + len(and_mask),
        0,
        0,
        0,
        0,
    )
    image = bitmap_info_header + xor_bitmap + and_mask
    icon_dir = ICO_HEADER + struct.pack("<H", 1)
    icon_dir_entry = struct.pack(
        "<BBBBHHII",
        ICON_SIZE,
        ICON_SIZE,
        0,
        0,
        1,
        32,
        len(image),
        6 + 16,
    )
    return icon_dir + icon_dir_entry + image


def main() -> None:
    ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = build_ico()
    if not data.startswith(ICO_HEADER):
        raise RuntimeError("generated icon has an invalid ICO header")
    ICON_PATH.write_bytes(data)
    print(f"Generated P14-C preview icon: {ICON_PATH} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
