"""Compile the local SCBKR Kernel Pack.

The Google Drive folder is treated as an author-kernel source. This module does
not perform RAG and does not convert Drive content into user evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

KERNEL_AUTHOR = "許文耀 / 沈耀"
KERNEL_NAME = "許文耀 / 沈耀 SCBKR Kernel"
SOURCE_ROLE = "AUTHOR_KERNEL_SOURCE"
DRIVE_FOLDER_URL = "https://drive.google.com/drive/folders/12VzOUJsgt68OXOoh1KukpQygJNfU_nn8"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KERNEL_PACK_PATH = REPO_ROOT / "kernel_pack" / "scbkr_kernel_pack.json"

REQUIRED_SECTIONS = [
    "L0_ZEROTH_THEOREM",
    "SCBKR_CORE",
    "VALIDITY_FAILURE_GATE",
    "OWNER_RECALL",
    "WORM_REPLAY",
    "DIRECT_COMPILER_RULES",
    "DRAFT_VALIDATOR_RULES",
    "PLAN_DEPTH_RULES",
    "FOUR_STORE_POLICY",
    "LOCAL_FIRST_PRIVACY_RULES",
    "USER_RESPONSIBILITY_RULES",
    "SHENYAO_KERNEL_ATTRIBUTION_RULES",
    "DUAL_SIGNATURE_RULES",
]


def default_kernel_pack() -> dict[str, Any]:
    return {
        "meta": {
            "author": KERNEL_AUTHOR,
            "source_role": SOURCE_ROLE,
            "kernel_authority": True,
            "generated_under_kernel": KERNEL_NAME,
            "user_data_local_only": True,
            "model_role": "draft_only",
            "drive_folder_url": DRIVE_FOLDER_URL,
        },
        "L0_ZEROTH_THEOREM": {
            "rule": "Any reusable judgement must become editable S/C/B/K/R before signature or storage.",
            "reject": ["unsigned formal authority", "model final judgement", "chat context as K basis"],
        },
        "SCBKR_CORE": {
            "S": "subject, situation, applicable and non-applicable contexts",
            "C": "causality, user judgement, why the rule exists",
            "B": "boundaries, forbidden actions, stop conditions",
            "K": "basis policy across LOGIC/CORPUS/MEMORY/VECTOR",
            "R": "responsibility, validity, failure, replay, repair, signature",
        },
        "VALIDITY_FAILURE_GATE": {
            "validity_required": ["formation_conditions", "failure_conditions", "replay_requirements", "repair_path"],
            "fail_on": ["template_empty", "missing_kernel_attribution", "model_overreach"],
        },
        "OWNER_RECALL": {
            "local_user_owns_rule": True,
            "kernel_is_structure_source": True,
            "model_never_owns_rule": True,
        },
        "WORM_REPLAY": {
            "record": ["route", "kernel_pack_version", "draft", "validator", "signature", "storage"],
        },
        "DIRECT_COMPILER_RULES": {
            "input_path": "user_input -> kernel_pack -> L0 Gate -> Direct SCBKR Compiler -> Validators -> PlanDepthCompiler -> Workbench",
            "forbid": ["case-specific fallback", "template success", "model signature"],
        },
        "DRAFT_VALIDATOR_RULES": {
            "required_dimensions": ["S", "C", "B", "K", "R"],
            "generic_empty_values": ["處理使用者需求", "依規則判斷", "不得違規", "依據資料", "使用者負責"],
        },
        "PLAN_DEPTH_RULES": {
            "FREE": ["basic five dimensions", "user self-sign", "local storage", "local citation"],
            "NT690": ["responsibility boundary", "missing data questions", "stop conditions", "draft-only conditions"],
            "NT3300": ["validity", "failure", "risk", "repair", "replay", "version", "dual signature", "rulepack"],
        },
        "FOUR_STORE_POLICY": {
            "LOGIC": "formal signed active rules",
            "CORPUS": "formal signed active data",
            "MEMORY": "signed active long-term preferences",
            "VECTOR": "recall only; never formal K basis",
        },
        "LOCAL_FIRST_PRIVACY_RULES": {
            "user_data_local_only": True,
            "cloud_scope": ["kernel update", "license check"],
        },
        "USER_RESPONSIBILITY_RULES": {
            "user_signature_required": True,
            "real_world_outcome_owner": "local_user",
            "model_execution_forbidden": True,
        },
        "SHENYAO_KERNEL_ATTRIBUTION_RULES": {
            "required_phrase": KERNEL_NAME,
            "author": KERNEL_AUTHOR,
            "kernel_provides_structure_not_user_outcome": True,
        },
        "DUAL_SIGNATURE_RULES": {
            "kernel_author": KERNEL_AUTHOR,
            "structure_source": "SCBKR Kernel",
            "local_user_signature_required": True,
            "kernel_structure_signature_optional": True,
        },
    }


def compile_kernel_pack(output_path: Path | None = None) -> dict[str, Any]:
    pack = default_kernel_pack()
    missing = [name for name in REQUIRED_SECTIONS if name not in pack]
    if missing:
        raise ValueError(f"kernel pack missing sections: {missing}")
    target = output_path or DEFAULT_KERNEL_PACK_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return pack


def load_kernel_pack(path: Path | None = None) -> dict[str, Any]:
    target = path or DEFAULT_KERNEL_PACK_PATH
    if not target.exists():
        return compile_kernel_pack(target)
    return json.loads(target.read_text(encoding="utf-8"))

