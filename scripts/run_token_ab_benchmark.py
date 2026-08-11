"""Run a same-model SCBKR A/B token benchmark against an OpenAI-compatible API."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib import error, request

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.metrics.token_ab_benchmark import run_token_ab_benchmark, write_token_ab_report


def make_openai_compatible_model_call(*, base_url: str, api_key: str, timeout: float):
    endpoint = base_url.rstrip("/") + "/chat/completions"

    def model_call(*, provider: str, model: str, messages: list[dict[str, str]], variant: str) -> dict[str, Any]:
        payload = json.dumps({"model": model, "messages": messages, "temperature": 0}, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json", "X-SCBKR-Benchmark-Variant": variant}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = request.Request(endpoint, data=payload, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{provider} returned HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"could not reach {provider} at {endpoint}: {exc.reason}") from exc

    return model_call


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="JSON file containing question, full_history, full_rule_context and current_rule_package")
    parser.add_argument("--provider", default="lm_studio")
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--api-key", default=os.getenv("SCBKR_BENCHMARK_API_KEY", ""))
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--output-json", default="reports/token_ab_benchmark.json")
    parser.add_argument("--output-markdown", default="reports/token_ab_benchmark.md")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    model_call = make_openai_compatible_model_call(base_url=args.base_url, api_key=args.api_key, timeout=args.timeout)
    report = run_token_ab_benchmark(
        question=str(source.get("question") or ""),
        full_history=list(source.get("full_history") or []),
        full_rule_context=source.get("full_rule_context") or {},
        current_rule_package=source.get("current_rule_package") or {},
        provider=args.provider,
        model_name=args.model,
        model_call=model_call,
    )
    json_path, markdown_path = write_token_ab_report(
        report,
        json_path=args.output_json,
        markdown_path=args.output_markdown,
    )
    print(json.dumps({
        "savings_verified": report["savings_verified"],
        "measurement_basis": report["measurement_basis"],
        "prompt_reduction_percent": report["savings"]["prompt"]["reduction_percent"],
        "total_reduction_percent": report["savings"]["total"]["reduction_percent"],
        "json_report": str(json_path),
        "markdown_report": str(markdown_path),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
