"""Run the 10 evaluation questions through the real RAG pipeline and score them.

    python evaluation/evaluate.py

Scoring (automated, deterministic):
  * Answerable question: correct if the answer is NOT the not-found message and
    contains every `must_include` group (any one alternative per group, case-
    insensitive, whole-number matching so "12" does not match "120").
  * Unanswerable question (`expect_not_found`): correct only if the pipeline
    returned the not-found message.
  * Accuracy = correct / total. Retrieval is reported separately and never counted.

Writes evaluation/results/eval_report.md and eval_results.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_QUESTIONS = HERE / "questions.json"
DEFAULT_OUTPUT = HERE / "results"
TARGET_ACCURACY = 0.85

# --------------------------------------------------------------------------- scoring

def normalize(text: str) -> str:
    text = text.lower().replace("–", "-").replace("—", "-").replace(" ", " ")
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)  # 1,200 -> 1200
    return re.sub(r"\s+", " ", text)


def contains_term(text: str, term: str) -> bool:
    """Case-insensitive match of `term` as a whole token ("12" is not found in "120" or "1.12")."""
    pattern = r"(?<![\w.])" + re.escape(normalize(term)) + r"(?!\w|\.\d)"
    return re.search(pattern, normalize(text)) is not None


def score_answer(question: dict, answer: str, found: bool) -> tuple[bool, str]:
    """Return (correct, human-readable reason)."""
    if question.get("expect_not_found"):
        if not found:
            return True, "correctly reported that the answer is not in the documents"
        return False, "answered a question whose answer is NOT in the documents (possible hallucination)"

    if not found:
        return False, "pipeline said the answer was not found"

    missing = [
        " / ".join(group)
        for group in question["must_include"]
        if not any(contains_term(answer, alt) for alt in group)
    ]
    if missing:
        return False, "missing required: " + "; ".join(missing)
    return True, "all required facts present"


def expected_sources(question: dict) -> list[str]:
    return [s.strip() for s in (question.get("source") or "").split(";") if s.strip()]


def summarize(results: list[dict]) -> dict:
    total = len(results)
    correct = sum(r["correct"] for r in results)
    return {
        "total": total,
        "correct": correct,
        "incorrect": total - correct,
        "accuracy": correct / total if total else 0.0,
        "target": TARGET_ACCURACY,
        "passed": total > 0 and correct / total >= TARGET_ACCURACY,
    }


def load_questions(path: Path) -> list[dict]:
    questions = json.loads(path.read_text(encoding="utf-8"))
    for q in questions:
        if not q.get("question"):
            raise ValueError(f"Question {q.get('id')} has no text")
        if not q.get("expect_not_found") and not q.get("must_include"):
            raise ValueError(f"Question {q['id']} needs 'must_include' or 'expect_not_found'")
    return questions


# --------------------------------------------------------------------------- report

def format_expected_source(source: str | None, page) -> str:
    """'a.pdf; b.pdf' + '1; 2' -> 'a.pdf, page 1; b.pdf, page 2'."""
    if not source:
        return "none (not in documents)"
    sources = [s.strip() for s in source.split(";")]
    pages = [p.strip() for p in str(page).split(";")] if page is not None else []
    return "; ".join(
        f"{s}, page {pages[i]}" if i < len(pages) and pages[i] else s for i, s in enumerate(sources)
    )


def write_report(results: list[dict], summary: dict, meta: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "eval_results.json").write_text(
        json.dumps({"meta": meta, "summary": summary, "results": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "# RAG Evaluation Report",
        "",
        f"- Run at: {meta['run_at']}",
        f"- Provider: `{meta['provider']}` | Embedding model: `{meta['embedding_model']}` | LLM: `{meta['llm_model']}` | "
        f"chunk size/overlap: {meta['chunk_size']}/{meta['chunk_overlap']} | top_k: {meta['top_k']}",
        f"- **Automated accuracy: {summary['correct']}/{summary['total']} = {summary['accuracy']:.0%}** "
        f"(target {summary['target']:.0%}: {'PASSED' if summary['passed'] else 'NOT MET'})",
        f"- Expected source document retrieved: {meta['retrieval_hits']}/{meta['retrieval_total']} "
        "answerable questions (informational only, not part of accuracy)",
        f"- API errors during the run: {meta['api_errors']} (counted as incorrect)",
        "",
        "Automated scoring checks that each answer contains the required facts (see `criteria`). "
        "The full answers are included below so they can be verified manually against the PDFs.",
        "",
        "| # | Result | Question | Reason |",
        "|---|--------|----------|--------|",
    ]
    for r in results:
        lines.append(f"| {r['id']} | {'PASS' if r['correct'] else 'FAIL'} | {r['question']} | {r['reason']} |")

    for r in results:
        lines += [
            "",
            f"## Q{r['id']} - {'PASS' if r['correct'] else 'FAIL'} ({r['category']})",
            "",
            f"**Question:** {r['question']}",
            "",
            f"**Expected:** {r['expected_answer']}  ",
            f"**Expected source:** {format_expected_source(r['expected_source'], r['expected_page'])}",
            "",
            f"**Criteria:** {r['criteria']}",
            "",
            f"**Pipeline answer:** {r['answer']}",
            "",
            f"**Cited sources:** {', '.join(r['cited_sources']) or '(none)'}  ",
            "**Retrieved chunks:** " + ", ".join(f"{x['reference']} (d={x['distance']:.3f})" for x in r["retrieved"]),
            "",
            f"**Scoring:** {r['reason']} ({r['latency_s']:.1f}s)",
        ]
    report = out_dir / "eval_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


# --------------------------------------------------------------------------- main

def run(questions_path: Path, out_dir: Path) -> int:
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    from rag_pipeline.config import Settings
    from rag_pipeline.pipeline import LLMError, RagAnswer, RagPipeline

    settings = Settings.from_env()
    pipeline = RagPipeline(settings)  # fails fast on missing key / empty index
    questions = load_questions(questions_path)

    results = []
    retrieval_hits = retrieval_total = api_errors = 0
    for q in questions:
        start = time.perf_counter()
        try:
            rag = pipeline.ask(q["question"])
            correct, reason = score_answer(q, rag.answer, rag.found)
        except LLMError as exc:
            # Counted as incorrect (never skipped), and clearly labelled as an API error.
            rag = RagAnswer(q["question"], f"[API ERROR] {exc}")
            correct, reason = False, "API error - no answer produced"
            api_errors += 1
        latency = time.perf_counter() - start

        retrieved_sources = {c.source for c in rag.retrieved}
        if not q.get("expect_not_found"):
            retrieval_total += 1
            retrieval_hits += all(s in retrieved_sources for s in expected_sources(q))

        results.append({
            "id": q["id"],
            "category": q.get("category", ""),
            "question": q["question"],
            "expected_answer": q["expected_answer"],
            "expected_source": q.get("source"),
            "expected_page": q.get("page"),
            "criteria": q.get("criteria", ""),
            "answer": rag.answer,
            "found": rag.found,
            "correct": correct,
            "reason": reason,
            "cited_sources": rag.references,
            "retrieved": [{"reference": c.reference, "distance": round(c.distance, 4)} for c in rag.retrieved],
            "latency_s": round(latency, 2),
        })
        print(f"[{'PASS' if correct else 'FAIL'}] Q{q['id']}: {q['question']}")
        print(f"        answer: {rag.answer}")
        if not correct:
            print(f"        reason: {reason}")

    summary = summarize(results)
    meta = {
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "provider": settings.provider,
        "embedding_model": settings.embedding_model,
        "llm_model": settings.llm_model,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "top_k": settings.top_k,
        "collection": settings.collection_name,
        "retrieval_hits": retrieval_hits,
        "retrieval_total": retrieval_total,
        "api_errors": api_errors,
    }
    report = write_report(results, summary, meta, out_dir)

    print("\n" + "=" * 60)
    print(f"Correct:   {summary['correct']}")
    print(f"Incorrect: {summary['incorrect']}")
    print(f"Accuracy:  {summary['correct']}/{summary['total']} = {summary['accuracy']:.0%} "
          f"(target >= {TARGET_ACCURACY:.0%}: {'PASSED' if summary['passed'] else 'NOT MET'})")
    if api_errors:
        print(f"WARNING:   {api_errors} question(s) failed with API errors (counted as incorrect). "
              "Fix the cause (e.g. rate limits: set LLM_REQUESTS_PER_MINUTE) and re-run.")
    print(f"Report:    {report}")
    return 0 if summary["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the RAG pipeline on the test questions")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        return run(args.questions, args.output_dir)
    except Exception as exc:  # show a clean one-line error instead of a traceback
        print(f"Evaluation could not run: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
