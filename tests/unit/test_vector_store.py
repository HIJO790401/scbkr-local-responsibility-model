from pathlib import Path
from core.retrieval import vector_store

def test_vector_store_fallback_no_crash_and_lazy_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    assert not (tmp_path / "vector").exists()
    status = vector_store.get_vector_store_status()
    assert status["cloud"] is False
    result = vector_store.upsert_retrieval_case({"case_id":"c","retrieval_text":"x","case_type":"success_case"})
    assert result["backend"] in ("deterministic_fallback", "chromadb")
    if result["backend"] == "deterministic_fallback":
        assert not (tmp_path / "vector").exists()
    query = vector_store.query_similar_cases("x")
    assert query["backend"] in ("deterministic_fallback", "chromadb")


def test_chromadb_candidates_are_deterministically_scored_and_routed(monkeypatch, tmp_path):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))

    class FakeCollection:
        def query(self, **kwargs):
            assert "query_embeddings" in kwargs
            assert "query_texts" not in kwargs
            return {"ids": [["case-1", "case-2"]], "documents": [["local retrieval API", "unrelated banana"]]}

    class FakeClient:
        def get_or_create_collection(self, *args, **kwargs):
            assert kwargs.get("embedding_function") is None
            return FakeCollection()

    monkeypatch.setattr(vector_store, "is_chromadb_available", lambda: True)
    monkeypatch.setattr(vector_store, "ensure_vector_store", lambda: FakeClient())

    result = vector_store.query_similar_cases("local retrieval API", top_k=2)

    assert result["backend"] == "chromadb"
    assert result["embedding_status"] == "local_chromadb_no_external_embedding"
    assert result["candidates"][0]["case_id"] == "case-1"
    assert all("score" in candidate for candidate in result["candidates"])
    assert all("route" in candidate for candidate in result["candidates"])
    assert all(candidate["backend"] == "chromadb" for candidate in result["candidates"])
    assert all(candidate["similarity_source"] == "deterministic_rescore_after_chromadb" for candidate in result["candidates"])
    assert result["candidates"][0]["route"] != "none"


def test_vector_case_builder_matches_closed_schema_shape():
    import json
    from core.retrieval.vector_case import build_vector_case_from_storage_plan

    schema = json.loads(Path("schemas/vector_case.schema.json").read_text(encoding="utf-8"))
    case = build_vector_case_from_storage_plan(
        {"task_id": "task-1", "task_type": "workflow", "task_name": "workflow audit", "raw_input": "raw"},
        {dimension: "summary" for dimension in ("S", "C", "B", "K", "R")},
        {"storage_plan_status": "storage_confirmed_plan"},
        case_id="case-1",
    )

    assert set(case) == set(schema["required"])
    assert "similarity_metadata" in case
    assert "raw_input" not in case
    assert "created_at" not in case
    assert set(case["similarity_metadata"]) == set(schema["properties"]["similarity_metadata"]["required"])


def _sample_case():
    return {"case_id": "case-secret", "retrieval_text": "local retrieval API", "case_type": "success_case", "task_id": "task-1"}


def _assert_fallback_unavailable(result):
    assert result["backend"] == "deterministic_fallback"
    assert result["status"] == "unavailable"
    assert result["embedding_status"] == "fallback_keyword"


def test_upsert_falls_back_when_persistent_client_raises(monkeypatch):
    monkeypatch.setattr(vector_store, "is_chromadb_available", lambda: True)
    monkeypatch.setattr(vector_store, "ensure_vector_store", lambda: (_ for _ in ()).throw(RuntimeError("PersistentClient failed api_key=abc token=def secret=ghi")))

    result = vector_store.upsert_retrieval_case(_sample_case())

    _assert_fallback_unavailable(result)
    assert "api_key" not in result["error_message"].lower()
    assert "token" not in result["error_message"].lower()
    assert "secret" not in result["error_message"].lower()


def test_upsert_falls_back_when_collection_creation_raises(monkeypatch):
    class FakeClient:
        def get_or_create_collection(self, *args, **kwargs):
            raise RuntimeError("collection creation failed")

    monkeypatch.setattr(vector_store, "is_chromadb_available", lambda: True)
    monkeypatch.setattr(vector_store, "ensure_vector_store", lambda: FakeClient())

    result = vector_store.upsert_retrieval_case(_sample_case())

    _assert_fallback_unavailable(result)


def test_upsert_falls_back_when_collection_upsert_raises(monkeypatch):
    class FakeCollection:
        def upsert(self, **kwargs):
            raise RuntimeError("upsert failed")

    class FakeClient:
        def get_or_create_collection(self, *args, **kwargs):
            return FakeCollection()

    monkeypatch.setattr(vector_store, "is_chromadb_available", lambda: True)
    monkeypatch.setattr(vector_store, "ensure_vector_store", lambda: FakeClient())

    result = vector_store.upsert_retrieval_case(_sample_case())

    _assert_fallback_unavailable(result)


def test_upsert_falls_back_when_vector_db_path_unwritable(monkeypatch):
    monkeypatch.setattr(vector_store, "is_chromadb_available", lambda: True)
    monkeypatch.setattr(vector_store, "ensure_vector_store", lambda: (_ for _ in ()).throw(PermissionError("vector_db path is not writable")))

    result = vector_store.upsert_retrieval_case(_sample_case())

    _assert_fallback_unavailable(result)
