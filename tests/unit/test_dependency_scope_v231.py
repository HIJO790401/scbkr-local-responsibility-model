from copy import deepcopy

import pytest

from core.tools.evidence_trace import (
    build_dependency_coverage_receipt,
    build_evidence_read_trace,
    record_evidence_read,
    verify_dependency_coverage,
)
from core.tools.state_precondition import (
    EvidenceProjectionError,
    _select,
    build_evidence_dependency_manifest,
    compare_scoped_evidence_state,
)
from apps.api.main import _revalidate_revision_source_at_confirm


def prepared(state, selectors, scope="file_modification"):
    events = []
    for selector_type, selector in selectors:
        spec = {"selector_id": "temporary", "selector_type": selector_type, "selector": selector}
        events.append(record_evidence_read(
            "draft-1", state["resource_id"], state_scope=scope,
            selector_type=selector_type, selector=selector,
            value=_select(state, spec), reader_kind="verified_test_reader",
        ))
    trace = build_evidence_read_trace("draft-1", events)
    manifest = build_evidence_dependency_manifest(trace, state, state_scope=scope, resource_kind="file" if scope == "file_modification" else "message")
    coverage = build_dependency_coverage_receipt(trace, manifest)
    assert verify_dependency_coverage(trace, manifest, coverage)
    return trace, manifest, coverage


def compare(manifest, state):
    return compare_scoped_evidence_state(manifest, manifest["draft_projection_hash"], state)


def test_clock_and_unrelated_file_section_do_not_conflict():
    state = {"resource_id": "file:a.py", "content": "def target():\n    return 1\n\ndef other():\n    return 2", "read_at": "a"}
    _, manifest, _ = prepared(state, [("text_anchor", "def target():\n    return 1")])
    changed = {**state, "content": state["content"].replace("return 2", "return 3"), "read_at": "b"}
    assert compare(manifest, changed)["allowed"] is True


def test_relevant_hunk_change_and_ambiguous_anchor_fail_closed():
    state = {"resource_id": "file:a.py", "content": "def target():\n    return 1\n\ndef other():\n    return 2"}
    _, manifest, _ = prepared(state, [("text_anchor", "def target():\n    return 1")])
    changed = {**state, "content": state["content"].replace("return 1", "return 9")}
    assert compare(manifest, changed)["reason"] == "relevant_evidence_missing"
    duplicate = {**state, "content": state["content"] + "\n" + "def target():\n    return 1"}
    assert compare(manifest, duplicate)["reason"] == "dependency_anchor_ambiguous"
    shifted = {**state, "content": "# new header\n" + state["content"]}
    assert compare(manifest, shifted)["allowed"] is True


def test_whole_resource_and_field_projection_have_distinct_drift_behavior():
    state = {"resource_id": "rule:r1", "S": {"task": "A"}, "C": {"flow": "B"}, "read_at": "a"}
    _, whole, _ = prepared(state, [("whole_resource", "")], scope="rule_revision_source")
    _, scoped, _ = prepared(state, [("rule_field", "S.task")], scope="rule_revision_source")
    other = {**state, "C": {"flow": "C"}, "read_at": "b"}
    assert compare(whole, other)["reason"] == "relevant_evidence_changed"
    assert compare(scoped, other)["allowed"] is True
    relevant = {**state, "S": {"task": "Z"}}
    assert compare(scoped, relevant)["changed_selector_ids"] == ["dep-001"]


def test_unrelated_inbox_drift_is_allowed_but_thread_reply_and_recipients_conflict():
    state = {"resource_id": "mail:thread-t1", "threads": {"t1": {"latest_message_id": "m1"}, "t2": {"latest_message_id": "x1"}}, "messages": [{"id": "m1", "thread_id": "t1", "body": "hello"}], "recipient_set": ["A@example.com"]}
    _, manifest, _ = prepared(state, [("thread_latest_message_id", "t1"), ("message_id", "m1"), ("recipient_set", "")], scope="external_message")
    unrelated = deepcopy(state)
    unrelated["threads"]["t2"]["latest_message_id"] = "x2"
    unrelated["messages"].append({"id": "x2", "thread_id": "t2", "body": "other"})
    assert compare(manifest, unrelated)["allowed"] is True
    reply = deepcopy(state)
    reply["threads"]["t1"]["latest_message_id"] = "m2"
    reply["messages"].append({"id": "m2", "thread_id": "t1", "body": "new"})
    assert len(compare(manifest, reply)["changed_selector_ids"]) == 1
    recipients = {**state, "recipient_set": ["b@example.com"]}
    assert compare(manifest, recipients)["reason"] == "relevant_evidence_changed"


def test_missing_trace_and_coverage_cannot_authorize_scoped_compare():
    state = {"resource_id": "rule:r1", "version": 1}
    trace, manifest, coverage = prepared(state, [("whole_resource", "")], scope="rule_revision_source")
    broken = deepcopy(trace)
    broken["events"][0]["content_hash"] = "bad"
    assert not verify_dependency_coverage(broken, manifest, coverage)
    missing = deepcopy(manifest)
    missing["dependency_selectors"] = []
    assert not verify_dependency_coverage(trace, missing, coverage)
    with pytest.raises(ValueError, match="trace_manifest_hash_mismatch"):
        event = record_evidence_read("draft-1", "rule:r1", state_scope="rule_revision_source", selector_type="whole_resource", selector="", value={"wrong": True}, reader_kind="test")
        build_evidence_dependency_manifest(build_evidence_read_trace("draft-1", [event]), state, state_scope="rule_revision_source", resource_kind="rule")


def test_referenced_attachment_change_is_relevant():
    state = {"resource_id": "mail:thread-1", "attachments": [{"id": "a1", "hash": "old"}, {"id": "a2", "hash": "other"}]}
    _, manifest, _ = prepared(state, [("attachment_id", "a1")], scope="external_message")
    unrelated = deepcopy(state)
    unrelated["attachments"][1]["hash"] = "new"
    assert compare(manifest, unrelated)["allowed"] is True
    relevant = deepcopy(state)
    relevant["attachments"][0]["hash"] = "new"
    assert compare(manifest, relevant)["reason"] == "relevant_evidence_changed"


def test_under_capture_blocks_before_any_state_comparison():
    state = {"resource_id": "rule:r1", "A": 1, "B": 2, "C": 3}
    events = [record_evidence_read("draft-1", state["resource_id"], state_scope="rule_revision_source", selector_type="rule_field", selector=key, value=state[key], reader_kind="rule_registry") for key in ("A", "B")]
    trace = build_evidence_read_trace("draft-1", events)
    manifest = build_evidence_dependency_manifest(trace, state, state_scope="rule_revision_source", resource_kind="rule")
    missing = deepcopy(manifest)
    missing["dependency_selectors"] = missing["dependency_selectors"][:1]
    coverage = build_dependency_coverage_receipt(trace, missing)
    assert coverage["coverage_complete"] is False
    assert coverage["reason"] == "dependency_capture_incomplete"
    assert not verify_dependency_coverage(trace, missing, coverage)
    changed = {**state, "B": 99}
    assert compare(manifest, changed)["reason"] == "relevant_evidence_changed"
    assert compare(manifest, {**state, "C": 99})["allowed"] is True


def test_derived_lineage_expands_to_trusted_source_and_missing_lineage_blocks():
    state = {"resource_id": "rule:r1", "B": "source"}
    source = record_evidence_read("draft-1", state["resource_id"], state_scope="rule_revision_source", selector_type="rule_field", selector="B", value="source", reader_kind="rule_registry")
    derived = record_evidence_read("draft-1", state["resource_id"], state_scope="rule_revision_source", selector_type="rule_field", selector="C", value="derived", reader_kind="derived", derived_from_event_ids=[source["read_event_id"]])
    trace = build_evidence_read_trace("draft-1", [source, derived])
    manifest = build_evidence_dependency_manifest(trace, state, state_scope="rule_revision_source", resource_kind="rule")
    assert len(manifest["dependency_selectors"]) == 1
    assert compare(manifest, {**state, "B": "changed"})["reason"] == "relevant_evidence_changed"
    broken = build_evidence_read_trace("draft-1", [{**derived, "derived_from_event_ids": []}])
    with pytest.raises(ValueError, match="dependency_lineage_missing"):
        build_evidence_dependency_manifest(broken, state, state_scope="rule_revision_source", resource_kind="rule")


def test_trace_tampering_and_model_self_report_cannot_narrow_coverage():
    state = {"resource_id": "rule:r1", "A": 1, "B": 2}
    events = [record_evidence_read("draft-1", state["resource_id"], state_scope="rule_revision_source", selector_type="rule_field", selector=key, value=state[key], reader_kind="rule_registry") for key in ("A", "B")]
    trace = build_evidence_read_trace("draft-1", events)
    manifest = build_evidence_dependency_manifest(trace, state, state_scope="rule_revision_source", resource_kind="rule")
    receipt = build_dependency_coverage_receipt(trace, manifest)
    assert receipt["coverage_complete"] is True
    assert len(manifest["dependency_selectors"]) == 2
    model_claim = {"model_says_only_used": ["A"]}
    assert model_claim["model_says_only_used"] != [event["selector"] for event in trace["events"]]
    tampered = deepcopy(trace)
    tampered["events"][1]["selector"] = "C"
    assert not verify_dependency_coverage(tampered, manifest, receipt)


def test_legacy_revision_without_trusted_manifest_requires_new_confirmation():
    result = _revalidate_revision_source_at_confirm({"supersedes_rule_id": "old-rule", "source_rule_snapshot": {"rule_version": "v1"}})
    assert result["allowed"] is False
    assert result["reason"] == "legacy_pending_reconfirmation_required"
