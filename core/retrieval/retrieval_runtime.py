"""P13-C retrieval orchestration; retrieval is advisory and never confirms or generates."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from core.ledger.ledger_event import build_ledger_event
from core.ledger.jsonl_ledger import append_ledger_event
from core.storage.sqlite_runtime import save_ledger_index, save_retrieval_case, list_retrieval_cases, save_retrieval_query_result, save_task, list_storage_items
from core.storage.runtime_paths import REPO_ROOT
from core.retrieval.case_builder import build_success_case_from_storage_item, build_memory_rule_case, hash_retrieval_text
from core.retrieval.similarity import rank_candidates, route_from_score
from core.retrieval.vector_store import upsert_retrieval_case, query_similar_cases, get_vector_store_status, is_chromadb_available
from core.retrieval.retrieval_result import new_query_id, now, query_hash

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
            status=upsert_retrieval_case(case)
            case.update({'backend': status.get('backend'), 'embedding_status': status.get('embedding_status')})
            save_retrieval_case(case); cases.append(case)
            if status.get('status')=='unavailable': _append('retrieval_fallback_used', task=task, payload={'case_id':case['case_id'],'backend':status.get('backend')})
        _append('retrieval_case_index_completed', task=task, payload={'candidate_count':len(cases),'backend':get_vector_store_status()['backend']})
        return {'indexed_cases': cases, 'backend_status': get_vector_store_status(), 'vector_db_created': (_data_dir()/ 'vector_db').exists()}
    except Exception as exc:
        _append('retrieval_case_index_failed', task=task, payload={'error_message':str(exc)})
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
        _append('retrieval_case_index_failed', task_id=memory_rule.get('task_id'), payload={'error_message':str(exc)})
        raise

def query_retrieval_cases(query_text: str, task_id: str | None=None, top_k: int=3, case_type: str | None=None) -> dict[str, Any]:
    if not str(query_text or '').strip(): raise ValueError('query_text is required')
    _append('retrieval_query_requested', task_id=task_id, payload={'top_k':top_k,'case_type':case_type})
    try:
        backend='deterministic_fallback'; candidates=[]
        if is_chromadb_available():
            res=query_similar_cases(query_text, top_k, case_type); backend=res.get('backend', backend); candidates=res.get('candidates', [])
        if not candidates or backend!='chromadb':
            if backend!='chromadb': _append('retrieval_fallback_used', task_id=task_id, payload={'backend':'deterministic_fallback'})
            candidates=rank_candidates(query_text, list_retrieval_cases(task_id=None, case_type=case_type, limit=200), top_k); backend='deterministic_fallback'
        route=route_from_score(candidates[0].get('score',0.0)) if candidates else 'none'
        result={'query_id':new_query_id(),'task_id':task_id,'query_text_hash':query_hash(query_text),'backend':backend,'route':route,'top_k':top_k,'candidates':candidates,'requires_user_confirmation':True,'auto_confirmed':False,'generation_allowed':False,'created_at':now()}
        save_retrieval_query_result(result); _append('retrieval_query_completed', task_id=task_id, payload={'backend':backend,'route':route,'top_k':top_k,'candidate_count':len(candidates)})
        return result
    except Exception as exc:
        _append('retrieval_query_failed', task_id=task_id, payload={'error_message':str(exc)})
        raise

def retrieve_for_task(task: dict[str, Any], top_k: int=3) -> dict[str, Any]:
    query='\n'.join(str(x) for x in [task.get('raw_input',''), task.get('task_type',''), task.get('scbkr',{}).get('draft_summary','')] if x)
    result=query_retrieval_cases(query, task_id=task.get('task_id'), top_k=top_k)
    task['retrieval_result']=result
    save_task(task)
    return result
