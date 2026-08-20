"""Build the production SCBKR Windows ICO from committed PNG assets."""

from __future__ import annotations

import struct
from pathlib import Path

ICON_DIR = Path("apps/desktop/src-tauri/icons")
ICON_PATH = ICON_DIR / "icon.ico"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def build_ico() -> bytes:
    """Build a multi-resolution ICO containing PNG-compressed images."""
    images: list[tuple[int, bytes]] = []
    for size in ICON_SIZES:
        source = ICON_DIR / f"icon-{size}.png"
        data = source.read_bytes()
        if not data.startswith(PNG_SIGNATURE):
            raise RuntimeError(f"invalid PNG icon asset: {source}")
        width, height = struct.unpack(">II", data[16:24])
        if (width, height) != (size, size):
            raise RuntimeError(
                f"icon asset size mismatch: {source} is {width}x{height}"
            )
        images.append((size, data))

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + (16 * len(images))
    entries: list[bytes] = []
    payloads: list[bytes] = []
    for size, data in images:
        dimension = 0 if size == 256 else size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                dimension,
                dimension,
                0,
                0,
                1,
                32,
                len(data),
                offset,
            )
        )
        payloads.append(data)
        offset += len(data)
    return header + b"".join(entries) + b"".join(payloads)


def main() -> None:
    ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = build_ico()
    if not data.startswith(b"\x00\x00\x01\x00"):
        raise RuntimeError("generated icon has an invalid ICO header")
    ICON_PATH.write_bytes(data)
    print(f"Generated SCBKR Windows icon: {ICON_PATH} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
