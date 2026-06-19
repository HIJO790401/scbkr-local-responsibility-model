from pathlib import Path
from core.retrieval import vector_store

def test_vector_store_fallback_no_crash_and_lazy_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    assert not (tmp_path / "vector_db").exists()
    status = vector_store.get_vector_store_status()
    assert status["cloud"] is False
    result = vector_store.upsert_retrieval_case({"case_id":"c","retrieval_text":"x","case_type":"success_case"})
    assert result["backend"] in ("deterministic_fallback", "chromadb")
    if result["backend"] == "deterministic_fallback":
        assert not (tmp_path / "vector_db").exists()
    query = vector_store.query_similar_cases("x")
    assert query["backend"] in ("deterministic_fallback", "chromadb")
