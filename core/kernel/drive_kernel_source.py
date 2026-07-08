"""Author-kernel source descriptor for the SCBKR Drive folder."""

from __future__ import annotations

from typing import Any

from .scbkr_kernel_compiler import DRIVE_FOLDER_URL, KERNEL_AUTHOR, SOURCE_ROLE


def author_kernel_source_descriptor() -> dict[str, Any]:
    return {
        "author": KERNEL_AUTHOR,
        "source_role": SOURCE_ROLE,
        "drive_folder_url": DRIVE_FOLDER_URL,
        "is_rag_source": False,
        "is_template_source": False,
        "is_case_database": False,
        "usage": "Compile local SCBKR Kernel Pack only.",
    }

