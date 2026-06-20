"""P13-C retrieval orchestration; retrieval is advisory and never confirms or generates."""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any
from core.ledger.ledger_event import build_ledger_event
from core.ledger.jsonl_ledger import append_ledger_event
from core.storage.sqlite_runtime import save_ledger_index, save_retrieval_case, list_retrieval_cases, save_retrieval_query_result, save_task, list_storage_items
from core.storage.runtime_paths import REPO_ROOT
from core.retrieval.case_builder import build_success_case_from_storage_item, build_memory_rule_case, hash_retrieval_text
from core.retrieval.similarity import rank_candidates, route_from_score, score_similarity
from core.retrieval.vector_store import upsert_retrieval_case, query_similar_cases, get_vector_store_status, is_chromadb_available
from core.retrieval.retrieval_result import new_query_id, now, query_hash

_SENSITIVE_ERROR_RE = re.compile(r"(?i)(api[_-]?key|token|secret|authorization|access[_-]?token|refresh[_-]?token)(\s*[=:]\s*)?[^\s,;]*")


def _sanitize_error_message(exc: BaseException) -> str:
    message = str(exc) or exc.__class__.__name__
    return _SENSITIVE_ERROR_RE.sub("[REDACTED]", message)[:500]


def _data_dir():
    import os
    return Path(os.environ.get("SCBKR_DATA_DIR", REPO_ROOT / "data")).expanduser()

def _append(event_type, task_id=None, payload=None, task=None):
    event=build_ledger_event(event_type, task_id=task_id or (task or {}).get('task_id'), trace_id=(task or {}).get('trace_id'), ledger_id=(task or {}).get('ledger_id'), payload=payload or {}, layer='RETRIEVAL')
    r=append_ledger_event(event); save_ledger_index(event, line_number=r['line_number'], jsonl_path=r['ledger_path']); return event

def _read_payload(relative_path):
    path=_data_dir()/relative_path
    with path.open(encoding='utf-8') as f: return json.load(f)

def index_task_storage_cases(task: dict[str, Any]) -> dict[str, Any]:
    _append('retrieval_case_index_requested', task=task, payload={'task_id': task.get('task_id')})
    try:
        if task.get('status')!='storage_committed' or task.get('physical_write_performed') is not True or task.get('review_passed') is not True:
            raise ValueError('storage_committed review_passed task with physical writes required')
        items=task.get('storage_items') or list_storage_items(task_id=task.get('task_id'), limit=50)
        cases=[]
        for item in items:
            if item.get('target') not in ('corpus','logic','exports'): continue
            payload=item.get('payload') or _read_payload(item['relative_path'])
            case=build_success_case_from_storage_item(task,item,payload)
            case.update({'backend': 'deterministic_fallback', 'embedding_status': 'fallback_keyword'})
            save_retrieval_case(case)
            status=upsert_retrieval_case(case)
            case.update({'backend': status.get('backend', 'deterministic_fallback'), 'embedding_status': status.get('embedding_status', 'fallback_keyword')})
            save_retrieval_case(case); cases.append(case)
            if status.get('status')=='unavailable':
                _append('retrieval_backend_unavailable', task=task, payload={'case_id':case['case_id'],'backend':status.get('backend'),'error_message':status.get('error_message')})
                _append('retrieval_fallback_used', task=task, payload={'case_id':case['case_id'],'backend':'deterministic_fallback'})
        _append('retrieval_case_index_completed', task=task, payload={'candidate_count':len(cases),'backend':get_vector_store_status()['backend']})
        return {'indexed_cases': cases, 'backend_status': get_vector_store_status(), 'vector_db_created': (_data_dir()/ 'vector_db').exists()}
    except Exception as exc:
        _append('retrieval_case_index_failed', task=task, payload={'error_message':_sanitize_error_message(exc)})
        raise

def index_memory_rule_case(memory_rule: dict[str, Any]) -> dict[str, Any]:
    _append('retrieval_case_index_requested', task_id=memory_rule.get('task_id'), payload={'case_type':'signed_memory_rule'})
    try:
        case=build_memory_rule_case(memory_rule); status=upsert_retrieval_case(case)
        case.update({'backend': status.get('backend'), 'embedding_status': status.get('embedding_status')})
        save_retrieval_case(case)
        _append('retrieval_case_index_completed', task_id=memory_rule.get('task_id'), payload={'case_id':case['case_id'],'case_type':case['case_type'],'backend':case.get('backend')})
        return case
    except Exception as exc:
        _append('retrieval_case_index_failed', task_id=memory_rule.get('task_id'), payload={'error_message':_sanitize_error_message(exc)})
        raise


def _candidate_retrieval_text(candidate: dict[str, Any]) -> str:
    return str(candidate.get('retrieval_text') or candidate.get('case_json', {}).get('retrieval_text') or '')


def _normalize_candidate(query_text: str, candidate: dict[str, Any], source_backend: str) -> dict[str, Any] | None:
    normalized = dict(candidate)
    retrieval_text = _candidate_retrieval_text(normalized).strip()
    case_id = normalized.get('case_id')
    if not case_id or not retrieval_text:
        return None
    score = score_similarity(query_text, retrieval_text)
    normalized.update(
        {
            'case_id': case_id,
            'retrieval_text': retrieval_text,
            'score': score,
            'route': route_from_score(score),
            'backend': source_backend,
            'similarity_source': 'deterministic_rescore',
        }
    )
    return normalized


def _metadata_completeness(candidate: dict[str, Any]) -> int:
    return sum(1 for value in candidate.values() if value not in (None, '', [], {}))


def _merge_candidate_sources(query_text: str, chroma_candidates: list[dict[str, Any]], sqlite_candidates: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    """Merge optional ChromaDB candidates with durable SQLite fallback candidates.

    Every candidate is deterministically rescored from its retrieval_text so the
    optional vector index can accelerate discovery but cannot decide final route.
    """
    merged_by_case_id: dict[str, dict[str, Any]] = {}
    for source_backend, source_candidates in (
        ('chromadb', chroma_candidates or []),
        ('deterministic_fallback', sqlite_candidates or []),
    ):
        for candidate in source_candidates:
            normalized = _normalize_candidate(query_text, candidate, source_backend)
            if normalized is None:
                continue
            existing = merged_by_case_id.get(normalized['case_id'])
            if existing is None:
                merged_by_case_id[normalized['case_id']] = normalized
                continue
            if (normalized['score'], _metadata_completeness(normalized)) > (existing['score'], _metadata_completeness(existing)):
                merged_by_case_id[normalized['case_id']] = normalized
    merged = list(merged_by_case_id.values())
    merged.sort(key=lambda item: (-float(item.get('score', 0.0)), item.get('case_id', '')))
    return merged[:max(0, int(top_k or 3))]


def _query_sqlite_fallback(query_text: str, case_type: str | None, top_k: int) -> list[dict[str, Any]]:
    # Score every durable SQLite fallback row before any top_k truncation so
    # older exact matches cannot be hidden by newest-row limits or ChromaDB.
    sqlite_cases = list_retrieval_cases(task_id=None, case_type=case_type, limit=None)
    return rank_candidates(query_text, sqlite_cases, top_k=len(sqlite_cases))


def query_retrieval_cases(query_text: str, task_id: str | None=None, top_k: int=3, case_type: str | None=None) -> dict[str, Any]:
    if not str(query_text or '').strip(): raise ValueError('query_text is required')
    _append('retrieval_query_requested', task_id=task_id, payload={'top_k':top_k,'case_type':case_type})
    try:
        chroma_candidates: list[dict[str, Any]] = []
        chroma_available = False
        chroma_failed = False
        if is_chromadb_available():
            chroma_available = True
            try:
                res=query_similar_cases(query_text, top_k, case_type)
                if res.get('backend') == 'chromadb':
                    chroma_candidates = res.get('candidates', []) or []
                elif res.get('status') in ('unavailable', 'fallback'):
                    chroma_failed = True
                    _append('retrieval_backend_unavailable', task_id=task_id, payload={'backend':res.get('backend', 'deterministic_fallback'), 'error_message':res.get('error_message', 'chromadb unavailable')})
                    _append('retrieval_fallback_used', task_id=task_id, payload={'backend':'deterministic_fallback'})
            except Exception as exc:
                chroma_failed = True
                _append('retrieval_backend_unavailable', task_id=task_id, payload={'backend':'chromadb','error_message':_sanitize_error_message(exc)})
                _append('retrieval_fallback_used', task_id=task_id, payload={'backend':'deterministic_fallback'})
        else:
            _append('retrieval_fallback_used', task_id=task_id, payload={'backend':'deterministic_fallback'})

        sqlite_candidates = _query_sqlite_fallback(query_text, case_type, top_k)
        candidates = _merge_candidate_sources(query_text, chroma_candidates, sqlite_candidates, top_k)

        if chroma_available and not chroma_failed:
            backend = 'merged_chromadb_sqlite' if sqlite_candidates else 'chromadb+sqlite_fallback_checked'
            _append('retrieval_fallback_merged', task_id=task_id, payload={'backend':backend,'chroma_candidate_count':len(chroma_candidates),'sqlite_candidate_count':len(sqlite_candidates),'merged_candidate_count':len(candidates)})
        else:
            backend = 'deterministic_fallback'

        route=route_from_score(candidates[0].get('score',0.0)) if candidates else 'none'
        result={'query_id':new_query_id(),'task_id':task_id,'query_text_hash':query_hash(query_text),'backend':backend,'route':route,'top_k':top_k,'candidates':candidates,'requires_user_confirmation':True,'auto_confirmed':False,'generation_allowed':False,'created_at':now()}
        save_retrieval_query_result(result); _append('retrieval_query_completed', task_id=task_id, payload={'backend':backend,'route':route,'top_k':top_k,'candidate_count':len(candidates)})
        return result
    except Exception as exc:
        _append('retrieval_query_failed', task_id=task_id, payload={'error_message':_sanitize_error_message(exc)})
        raise

def retrieve_for_task(task: dict[str, Any], top_k: int=3) -> dict[str, Any]:
    query='\n'.join(str(x) for x in [task.get('raw_input',''), task.get('task_type',''), task.get('scbkr',{}).get('draft_summary','')] if x)
    result=query_retrieval_cases(query, task_id=task.get('task_id'), top_k=top_k)
    task['retrieval_result']=result
    save_task(task)
    return result
