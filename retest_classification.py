#!/usr/bin/env python3
"""
Retest category/subject classification via /api/chat-stream and generate custom cases.
"""

import argparse
import ast
import json
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import requests

API_BASE_URL = "http://localhost:8001"
BATCH_SIZE = 10
DELAY_BETWEEN_REQUESTS = 0.5
DEFAULT_CASES_OUTPUT = "custom_cases_from_chunks.json"
DEFAULT_LOGS_FILE = "logs_live_from_api.json"

RETRIEVAL_CATEGORIES = {
    "thu_tuc_hanh_chinh",
    "to_chuc_bo_may",
    "thong_tin_tong_quan",
    "phan_anh_kien_nghi",
}
INTERACTION_CATEGORY = "tuong_tac"


def extract_multi_intent_shadow(reason_text: Optional[str]) -> Optional[Dict]:
    """Extract multi-intent shadow telemetry from log reason field."""
    if not reason_text:
        return None
    reason_text = str(reason_text)
    match = re.search(r"\[multi_intent_shadow\](.+?)(?:\s*$|\s*\|)", reason_text)
    if not match:
        return None
    try:
        shadow_json = json.loads(match.group(1))
        return shadow_json
    except json.JSONDecodeError:
        return None


def parse_shadow_from_log(log_text: str) -> Optional[Dict]:
    """Parse shadow payload from stream log line.

    Supports both:
    - "Multi-intent shadow: {...}" (Python dict repr)
    - "[multi_intent_shadow]{...}" (JSON payload in reason)
    """
    if not log_text:
        return None

    marker = "Multi-intent shadow:"
    if marker in log_text:
        payload = log_text.split(marker, 1)[1].strip()
        if payload:
            try:
                parsed = ast.literal_eval(payload)
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, SyntaxError):
                pass

    return extract_multi_intent_shadow(log_text)


def compute_primary_intent_accuracy(expected_category: Optional[str], expected_subject: Optional[str], shadow: Optional[Dict]) -> bool:
    """Check if primary intent from shadow matches expected category/subject."""
    if not shadow or shadow.get("intent_count", 0) < 1:
        return False
    
    primary_intent = shadow.get("primary_intent") or {}
    actual_category = primary_intent.get("category")
    actual_subject = primary_intent.get("subject")
    
    if expected_category != actual_category:
        return False
    if expected_subject != actual_subject:
        return False
    
    return True


def compute_multi_intent_stats(results: List[Dict]) -> Dict[str, any]:
    """Compute accuracy metrics for multi-intent vs single-intent cases."""
    multi_intent_results = [r for r in results if r.get("shadow") and r["shadow"].get("is_multi_intent")]
    single_intent_results = [r for r in results if not (r.get("shadow") and r["shadow"].get("is_multi_intent"))]
    
    multi_intent_count = len(multi_intent_results)
    single_intent_count = len(single_intent_results)
    
    multi_intent_primary_correct = sum(1 for r in multi_intent_results if compute_primary_intent_accuracy(r.get("expected_category"), r.get("expected_subject"), r.get("shadow")))
    single_intent_correct = sum(1 for r in single_intent_results if r.get("category_match") and r.get("subject_match"))
    
    stats = {
        "multi_intent_count": multi_intent_count,
        "single_intent_count": single_intent_count,
        "multi_intent_primary_correct": multi_intent_primary_correct,
        "multi_intent_accuracy": (multi_intent_primary_correct / multi_intent_count * 100 if multi_intent_count > 0 else 0),
        "single_intent_correct": single_intent_correct,
        "single_intent_accuracy": (single_intent_correct / single_intent_count * 100 if single_intent_count > 0 else 0),
        "conflict_cases": sum(1 for r in multi_intent_results if r.get("shadow", {}).get("has_conflict")),
        "clarify_secondary_count": sum(1 for r in multi_intent_results if r.get("shadow", {}).get("secondary_policy") == "clarify"),
    }
    return stats


def _shadow_primary_matches_expected(row: Dict) -> bool:
    shadow = row.get("shadow") or {}
    primary = shadow.get("primary_intent") or {}
    return (
        row.get("expected_category") == primary.get("category")
        and row.get("expected_subject") == primary.get("subject")
    )


def compute_shadow_vs_legacy_diff_stats(results: List[Dict]) -> Dict[str, any]:
    """Compare legacy single-label output vs shadow primary intent on multi-intent rows."""
    rows = [
        r
        for r in results
        if (r.get("shadow") or {}).get("is_multi_intent")
        and not r.get("dataset_issue")
        and r.get("expected_lane") == "retrieval"
    ]

    improved_cases: List[Dict] = []
    regressed_cases: List[Dict] = []

    both_correct = 0
    both_wrong = 0
    legacy_only = 0
    shadow_only = 0

    for row in rows:
        legacy_ok = bool(row.get("overall_match"))
        shadow_ok = _shadow_primary_matches_expected(row)

        if legacy_ok and shadow_ok:
            both_correct += 1
        elif (not legacy_ok) and (not shadow_ok):
            both_wrong += 1
        elif (not legacy_ok) and shadow_ok:
            shadow_only += 1
            improved_cases.append(row)
        elif legacy_ok and (not shadow_ok):
            legacy_only += 1
            regressed_cases.append(row)

    total = len(rows)
    return {
        "total_compared": total,
        "both_correct": both_correct,
        "both_wrong": both_wrong,
        "shadow_only_correct": shadow_only,
        "legacy_only_correct": legacy_only,
        "improved_cases": improved_cases,
        "regressed_cases": regressed_cases,
        "shadow_win_rate": (shadow_only / total * 100 if total else 0),
        "legacy_win_rate": (legacy_only / total * 100 if total else 0),
    }


def load_logs(file_path: str = DEFAULT_LOGS_FILE) -> List[Dict]:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("logs", [])


def load_custom_cases(file_path: str) -> List[Dict]:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("cases", [])


def fetch_chunks_from_api(api_base_url: str) -> List[Dict]:
    url = f"{api_base_url}/api/get-chunks"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    payload = response.json()
    chunks = payload.get("chunks", [])
    if not isinstance(chunks, list):
        return []
    return chunks


def build_taxonomy_from_chunks(chunks: List[Dict]) -> Dict[str, Set[str]]:
    taxonomy: Dict[str, Set[str]] = {}
    for chunk in chunks:
        category = chunk.get("category")
        subject = chunk.get("subject")
        if not category:
            continue
        taxonomy.setdefault(category, set())
        if subject:
            taxonomy[category].add(subject)
    return taxonomy


def infer_expected_lane(expected_category: Optional[str], expected_subject: Optional[str]) -> str:
    if expected_category == INTERACTION_CATEGORY:
        return "interaction"
    if expected_category is None and expected_subject is None:
        return "policy_null"
    return "retrieval"


def evaluate_case_match(
    expected_category: Optional[str],
    expected_subject: Optional[str],
    actual_category: Optional[str],
    actual_subject: Optional[str],
    actual_event_type: Optional[str],
) -> Tuple[bool, bool, bool]:
    lane = infer_expected_lane(expected_category, expected_subject)

    category_match = actual_category == expected_category
    subject_match = actual_subject == expected_subject

    if lane == "retrieval":
        return category_match and subject_match, category_match, subject_match

    if lane == "interaction":
        interaction_ok = actual_category == INTERACTION_CATEGORY or actual_event_type == "complaint"
        return interaction_ok, interaction_ok, True

    # policy_null lane: only care the system recognized a non-retrieval/policy path.
    policy_ok = (actual_category is None and actual_subject is None) or actual_event_type in {
        "out_of_scope",
        "qa_need_info",
        "banned_topic",
        "complaint",
    }
    return policy_ok, policy_ok, True


def validate_custom_cases(
    cases: List[Dict], taxonomy: Dict[str, Set[str]]
) -> Tuple[List[Dict], Dict[str, int]]:
    issues: List[Dict] = []
    stats = {
        "invalid_category": 0,
        "invalid_subject": 0,
        "interaction_cases": 0,
        "policy_null_cases": 0,
        "retrieval_cases": 0,
    }

    for case in cases:
        expected_category = case.get("expected_category")
        expected_subject = case.get("expected_subject")
        lane = infer_expected_lane(expected_category, expected_subject)

        if lane == "interaction":
            stats["interaction_cases"] += 1
            continue
        if lane == "policy_null":
            stats["policy_null_cases"] += 1
            continue

        stats["retrieval_cases"] += 1
        if expected_category not in taxonomy:
            stats["invalid_category"] += 1
            issues.append(
                {
                    "case_id": case.get("id"),
                    "issue": "invalid_category",
                    "expected_category": expected_category,
                    "expected_subject": expected_subject,
                    "query": case.get("query"),
                }
            )
            continue

        if expected_subject is not None and expected_subject not in taxonomy.get(expected_category, set()):
            stats["invalid_subject"] += 1
            issues.append(
                {
                    "case_id": case.get("id"),
                    "issue": "invalid_subject",
                    "expected_category": expected_category,
                    "expected_subject": expected_subject,
                    "query": case.get("query"),
                }
            )

    return issues, stats


def parse_stream_response(stream_text: str) -> Dict:
    result = {
        "category": None,
        "subject": None,
        "event_type": "normal",
        "need_llm": False,
        "llm_used": False,
        "expanded_query": None,
        "normalized_query": None,
        "shadow": None,
        "raw_response": stream_text,
    }

    def _clean_label(value):
        if value is None:
            return None
        s = str(value).strip()
        if not s or s.lower() in ("none", "null", "unknown", "n/a"):
            return None
        return s

    lines = stream_text.strip().split("\n")
    for line in lines:
        if not line.startswith("data: "):
            continue

        try:
            data = json.loads(line[6:])
        except json.JSONDecodeError:
            continue

        if "log" in data:
            log = data["log"]

            if isinstance(log, dict):
                result["category"] = _clean_label(log.get("detected_category"))
                result["subject"] = _clean_label(log.get("detected_subject"))
                result["event_type"] = log.get("event_type", "normal")
                result["expanded_query"] = log.get("expanded_query")

            elif isinstance(log, str):
                cat_match = re.search(r"Category:\s*([^,]+)", log)
                if cat_match:
                    maybe_cat = _clean_label(cat_match.group(1))
                    if maybe_cat is not None:
                        result["category"] = maybe_cat

                subj_match = re.search(r"Subject:\s*([^,]+)$", log)
                if subj_match:
                    maybe_sub = _clean_label(subj_match.group(1))
                    if maybe_sub is not None:
                        result["subject"] = maybe_sub

                if "'normalized':" in log or '"normalized":' in log:
                    norm_match = re.search(r"'normalized':\s*'([^']+)'", log)
                    if norm_match:
                        result["normalized_query"] = norm_match.group(1)

                if "'expanded':" in log or '"expanded":' in log:
                    exp_match = re.search(r"'expanded':\s*'([^']+)'", log)
                    if exp_match:
                        result["expanded_query"] = exp_match.group(1)

                if "Multi-intent shadow:" in log or "multi_intent_shadow" in log:
                    shadow_data = parse_shadow_from_log(log)
                    if shadow_data:
                        result["shadow"] = shadow_data

                log_lower = log.lower()
                if (
                    "[blocked]" in log_lower
                    or "query bi chan" in log_lower
                    or "chu de cam" in log_lower
                    or "ch\u1ee7 \u0111\u1ec1 c\u1ea5m" in log_lower
                    or "nhay cam" in log_lower
                    or "nh\u1ea1y c\u1ea3m" in log_lower
                ):
                    result["event_type"] = "banned_topic"
                elif (
                    "ngoai pham vi" in log_lower
                    or "ngo\u00e0i ph\u1ea1m vi" in log_lower
                    or "out_of_scope" in log_lower
                    or "=> ngo\u00e0i ph\u1ea1m vi" in log_lower
                ):
                    result["event_type"] = "out_of_scope"
                elif "can them thong tin" in log_lower or "qa_need_info" in log_lower:
                    result["event_type"] = "qa_need_info"
                elif "phan loai tuong tac - phan nan" in log_lower:
                    result["event_type"] = "complaint"

                if "bo qua nhan phan_nan" in log_lower:
                    if result.get("category") == "tuong_tac" and result.get("subject") == "phan_nan":
                        result["category"] = None
                        result["subject"] = None

                if "bat dau su dung llm" in log_lower or "llm classify" in log_lower:
                    result["llm_used"] = True

        if "replies" in data:
            replies = data["replies"]
            if isinstance(replies, list):
                for reply in replies:
                    reply_text = str(reply)
                    if "llm" in reply_text.lower() or "fallback" in reply_text.lower():
                        result["llm_used"] = True
            else:
                reply_text = str(replies)
                if "llm" in reply_text.lower() or "fallback" in reply_text.lower():
                    result["llm_used"] = True

    if "bat dau su dung llm" in stream_text.lower() or "llm classify" in stream_text.lower():
        result["llm_used"] = True
    result["need_llm"] = result["llm_used"]

    return result


def retest_single_query(query: str, session_id: str) -> Optional[Dict]:
    url = f"{API_BASE_URL}/api/chat-stream"
    payload = {
        "message": query,
        "session_id": session_id,
        "use_llm": True,
        "chunk_limit": 1,
    }

    try:
        start_time = time.time()
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            stream=True,
            timeout=30,
        )
        response.raise_for_status()

        stream_content = ""
        for line in response.iter_lines():
            if line:
                decoded = line.decode("utf-8")
                stream_content += decoded + "\n"

        response_time = time.time() - start_time

        parsed = parse_stream_response(stream_content)
        parsed["response_time_s"] = round(response_time, 2)

        return parsed

    except requests.exceptions.RequestException as e:
        print(f"Error calling API: {e}")
        return None


def save_results(results: List[Dict], run_id: str):
    output = {
        "run_id": run_id,
        "total_queries": len(results),
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }

    filename = f"retest_results_{run_id}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


def analyze_results(results: List[Dict]):
    if not results:
        return

    categories = {}
    subjects = {}
    event_types = {}
    llm_used_count = 0
    category_changes = 0
    subject_changes = 0

    for row in results:
        cat = row.get("category") or "null"
        subj = row.get("subject") or "null"
        evt = row.get("event_type", "normal")

        categories[cat] = categories.get(cat, 0) + 1
        subjects[subj] = subjects.get(subj, 0) + 1
        event_types[evt] = event_types.get(evt, 0) + 1

        if row.get("llm_used"):
            llm_used_count += 1

        if row.get("category") != row.get("old_category"):
            category_changes += 1
        if row.get("subject") != row.get("old_subject"):
            subject_changes += 1

    print("\nCategory distribution:")
    for cat, count in sorted(categories.items(), key=lambda item: -item[1])[:10]:
        print(f"  {cat}: {count} ({count / len(results) * 100:.1f}%)")

    print("\nSubject distribution (top 10):")
    for subj, count in sorted(subjects.items(), key=lambda item: -item[1])[:10]:
        print(f"  {subj}: {count} ({count / len(results) * 100:.1f}%)")

    print("\nEvent types:")
    for evt, count in event_types.items():
        print(f"  {evt}: {count} ({count / len(results) * 100:.1f}%)")

    print("\nLLM usage:")
    print(f"  LLM used: {llm_used_count} ({llm_used_count / len(results) * 100:.1f}%)")

    print("\nChanges from old labels:")
    print(f"  Category changed: {category_changes} ({category_changes / len(results) * 100:.1f}%)")
    print(f"  Subject changed: {subject_changes} ({subject_changes / len(results) * 100:.1f}%)")


def analyze_custom_results(results: List[Dict]):
    if not results:
        return

    scored_rows = [row for row in results if not row.get("dataset_issue")]
    total = len(scored_rows)
    passed = sum(1 for row in scored_rows if row.get("overall_match"))
    mismatches = [
        row for row in scored_rows if not row.get("overall_match")
    ]

    lane_stats: Dict[str, Dict[str, int]] = {}
    for row in scored_rows:
        lane = row.get("expected_lane") or "unknown"
        s = lane_stats.setdefault(lane, {"total": 0, "passed": 0})
        s["total"] += 1
        if row.get("overall_match"):
            s["passed"] += 1

    dataset_issues = [row for row in results if row.get("dataset_issue")]

    tag_stats: Dict[str, Dict[str, int]] = {}
    for row in scored_rows:
        tag = row.get("tag") or "untagged"
        stats = tag_stats.setdefault(tag, {"total": 0, "passed": 0})
        stats["total"] += 1
        if row.get("overall_match"):
            stats["passed"] += 1

    if total == 0:
        print("\nCustom corpus pass rate: no scored rows (all dataset issues)")
    else:
        print(f"\nCustom corpus pass rate: {passed}/{total} ({passed / total * 100:.1f}%)")

    print("\nScoreboard by lane:")
    for lane, s in sorted(lane_stats.items(), key=lambda item: item[0]):
        rate = s["passed"] / s["total"] * 100 if s["total"] else 0
        print(f"  {lane}: {s['passed']}/{s['total']} ({rate:.1f}%)")

    if dataset_issues:
        print(f"\nDataset issues (excluded from score): {len(dataset_issues)}")
        for row in dataset_issues[:20]:
            print(
                f"  {row.get('case_id')}: {row.get('dataset_issue_reason')} "
                f"expected=({row.get('expected_category')}, {row.get('expected_subject')})"
            )

    print("\nPass rate by tag:")
    for tag, stats in sorted(tag_stats.items(), key=lambda item: (item[0], -item[1]["total"])):
        rate = stats["passed"] / stats["total"] * 100 if stats["total"] else 0
        print(f"  {tag}: {stats['passed']}/{stats['total']} ({rate:.1f}%)")

    if mismatches:
        print("\nMismatches:")
        for row in mismatches:
            print(
                    f"  {row.get('case_id')}: lane={row.get('expected_lane')} "
                    f"expected=({row.get('expected_category')}, {row.get('expected_subject')}) "
                    f"actual=({row.get('category')}, {row.get('subject')}) "
                    f"event={row.get('event_type')} tag={row.get('tag')}"
            )

    multi_intent_stats = compute_multi_intent_stats(results)
    if multi_intent_stats.get("multi_intent_count", 0) > 0:
        print("\n" + "=" * 80)
        print("MULTI-INTENT ANALYSIS")
        print("=" * 80)
        print(f"Multi-intent queries: {multi_intent_stats['multi_intent_count']}")
        print(f"Single-intent queries: {multi_intent_stats['single_intent_count']}")
        print(f"\nPrimary intent accuracy (multi-intent): {multi_intent_stats['multi_intent_accuracy']:.1f}% ({multi_intent_stats['multi_intent_primary_correct']}/{multi_intent_stats['multi_intent_count']})")
        print(f"Single-intent accuracy: {multi_intent_stats['single_intent_accuracy']:.1f}% ({multi_intent_stats['single_intent_correct']}/{multi_intent_stats['single_intent_count']})")
        print(f"Conflict cases: {multi_intent_stats['conflict_cases']}")
        print(f"Clarify-first secondary count: {multi_intent_stats['clarify_secondary_count']}")

    diff_stats = compute_shadow_vs_legacy_diff_stats(results)
    if diff_stats.get("total_compared", 0) > 0:
        print("\n" + "=" * 80)
        print("LEGACY VS SHADOW (MULTI-INTENT RETRIEVAL CASES)")
        print("=" * 80)
        print(f"Compared rows: {diff_stats['total_compared']}")
        print(f"Both correct: {diff_stats['both_correct']}")
        print(f"Both wrong: {diff_stats['both_wrong']}")
        print(
            "Shadow-only correct (improvement): "
            f"{diff_stats['shadow_only_correct']} ({diff_stats['shadow_win_rate']:.1f}%)"
        )
        print(
            "Legacy-only correct (regression risk): "
            f"{diff_stats['legacy_only_correct']} ({diff_stats['legacy_win_rate']:.1f}%)"
        )

        if diff_stats["improved_cases"]:
            print("\nTop improved examples (legacy wrong -> shadow primary correct):")
            for row in diff_stats["improved_cases"][:10]:
                primary = (row.get("shadow") or {}).get("primary_intent") or {}
                print(
                    f"  {row.get('case_id')}: expected=({row.get('expected_category')}, {row.get('expected_subject')}) "
                    f"legacy=({row.get('category')}, {row.get('subject')}) "
                    f"shadow_primary=({primary.get('category')}, {primary.get('subject')}) "
                    f"query={row.get('query')}"
                )

        if diff_stats["regressed_cases"]:
            print("\nTop regression-risk examples (legacy correct -> shadow primary wrong):")
            for row in diff_stats["regressed_cases"][:10]:
                primary = (row.get("shadow") or {}).get("primary_intent") or {}
                print(
                    f"  {row.get('case_id')}: expected=({row.get('expected_category')}, {row.get('expected_subject')}) "
                    f"legacy=({row.get('category')}, {row.get('subject')}) "
                    f"shadow_primary=({primary.get('category')}, {primary.get('subject')}) "
                    f"query={row.get('query')}"
                )


def run_retest(max_queries: Optional[int] = None, logs_file: str = DEFAULT_LOGS_FILE):
    print("=" * 80)
    print("RETEST CLASSIFICATION via /api/chat-stream")
    print("=" * 80)

    logs = load_logs(logs_file)
    total = len(logs)
    print(f"\nLoaded {total} log entries from {logs_file}")

    if max_queries:
        logs = logs[:max_queries]
        print(f"  Limiting to first {max_queries} queries")

    results = []
    run_id = f"retest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    print(f"\nStarting retest (batch size: {BATCH_SIZE}, delay: {DELAY_BETWEEN_REQUESTS}s)")
    print("-" * 80)

    for idx, log_entry in enumerate(logs, 1):
        raw_query = log_entry.get("raw_query", "")
        if not raw_query:
            continue

        session_id = f"{run_id}_query_{idx}"
        print(f"\n[{idx}/{len(logs)}] Testing: {raw_query[:60]}...")

        retest_result = retest_single_query(raw_query, session_id)

        if retest_result:
            result_entry = {
                "run_id": run_id,
                "query_index": idx,
                "session_id": session_id,
                "original_log_id": log_entry.get("id"),
                "query": raw_query,
                "expanded_query": retest_result.get("expanded_query"),
                "normalized_query": retest_result.get("normalized_query"),
                "category": retest_result.get("category"),
                "subject": retest_result.get("subject"),
                "event_type": retest_result.get("event_type"),
                "need_llm": retest_result.get("need_llm"),
                "llm_used": retest_result.get("llm_used"),
                "response_time_s": retest_result.get("response_time_s"),
                "old_category": log_entry.get("detected_category"),
                "old_subject": log_entry.get("detected_subject"),
                "old_event_type": log_entry.get("event_type"),
                "timestamp": datetime.now().isoformat(),
            }
            results.append(result_entry)

            print(f"  Category: {retest_result.get('category')}")
            print(f"  Subject: {retest_result.get('subject')}")
            print(f"  Event: {retest_result.get('event_type')}")
            print(f"  LLM used: {retest_result.get('llm_used')}")
            print(f"  Time: {retest_result.get('response_time_s')}s")

            if retest_result.get("category") != log_entry.get("detected_category"):
                print(
                    "  Category changed: "
                    f"{log_entry.get('detected_category')} -> {retest_result.get('category')}"
                )
            if retest_result.get("subject") != log_entry.get("detected_subject"):
                print(
                    "  Subject changed: "
                    f"{log_entry.get('detected_subject')} -> {retest_result.get('subject')}"
                )
        else:
            print("  Failed to retest")

        if idx < len(logs):
            time.sleep(DELAY_BETWEEN_REQUESTS)

        if idx % BATCH_SIZE == 0:
            save_results(results, run_id)
            print(f"\nSaved intermediate results ({len(results)} entries)")

    save_results(results, run_id)

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total queries tested: {len(results)}")
    print(f"Results saved to: retest_results_{run_id}.json")

    analyze_results(results)


def run_custom_retest(cases_file: str, max_queries: Optional[int] = None):
    print("=" * 80)
    print("CUSTOM RETEST CLASSIFICATION via /api/chat-stream")
    print("=" * 80)

    cases = load_custom_cases(cases_file)
    total = len(cases)
    print(f"\nLoaded {total} custom cases from {cases_file}")

    taxonomy = build_taxonomy_from_chunks(fetch_chunks_from_api(API_BASE_URL))
    issues, issue_stats = validate_custom_cases(cases, taxonomy)
    issue_map = {item["case_id"]: item for item in issues}
    print(
        "Taxonomy validation: "
        f"retrieval={issue_stats['retrieval_cases']}, "
        f"interaction={issue_stats['interaction_cases']}, "
        f"policy_null={issue_stats['policy_null_cases']}, "
        f"invalid_category={issue_stats['invalid_category']}, "
        f"invalid_subject={issue_stats['invalid_subject']}"
    )

    if max_queries:
        cases = cases[:max_queries]
        print(f"  Limiting to first {max_queries} cases")

    results = []
    run_id = f"custom_retest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    print(f"\nStarting custom retest (batch size: {BATCH_SIZE}, delay: {DELAY_BETWEEN_REQUESTS}s)")
    print("-" * 80)

    for idx, case in enumerate(cases, 1):
        query = case.get("query", "")
        if not query:
            continue

        session_id = f"{run_id}_query_{idx}"
        print(f"\n[{idx}/{len(cases)}] Testing {case.get('id')}: {query[:60]}...")

        retest_result = retest_single_query(query, session_id)
        if retest_result:
            category = retest_result.get("category")
            subject = retest_result.get("subject")
            expected_category = case.get("expected_category")
            expected_subject = case.get("expected_subject")
            expected_lane = infer_expected_lane(expected_category, expected_subject)
            dataset_issue = issue_map.get(case.get("id"))

            overall_match, category_match, subject_match = evaluate_case_match(
                expected_category=expected_category,
                expected_subject=expected_subject,
                actual_category=category,
                actual_subject=subject,
                actual_event_type=retest_result.get("event_type"),
            )

            if dataset_issue:
                overall_match = False
                category_match = False
                subject_match = False

            result_entry = {
                "run_id": run_id,
                "query_index": idx,
                "session_id": session_id,
                "case_id": case.get("id"),
                "tag": case.get("tag"),
                "query": query,
                "expected_category": expected_category,
                "expected_subject": expected_subject,
                "expected_lane": expected_lane,
                "category": category,
                "subject": subject,
                "event_type": retest_result.get("event_type"),
                "need_llm": retest_result.get("need_llm"),
                "llm_used": retest_result.get("llm_used"),
                "expanded_query": retest_result.get("expanded_query"),
                "normalized_query": retest_result.get("normalized_query"),
                "response_time_s": retest_result.get("response_time_s"),
                "category_match": category_match,
                "subject_match": subject_match,
                "overall_match": overall_match,
                "shadow": retest_result.get("shadow"),
                "dataset_issue": bool(dataset_issue),
                "dataset_issue_reason": dataset_issue.get("issue") if dataset_issue else None,
                "timestamp": datetime.now().isoformat(),
            }
            results.append(result_entry)

            print(f"  Category: {category} | expected: {expected_category}")
            print(f"  Subject: {subject} | expected: {expected_subject}")
            print(
                f"  Match: cat={result_entry['category_match']} "
                f"subj={result_entry['subject_match']} overall={result_entry['overall_match']}"
            )
            print(
                f"  LLM used: {retest_result.get('llm_used')} | "
                f"Time: {retest_result.get('response_time_s')}s"
            )
            if result_entry["dataset_issue"]:
                print(f"  Dataset issue: {result_entry['dataset_issue_reason']} (excluded from score)")
        else:
            print("  Failed to retest")

        if idx < len(cases):
            time.sleep(DELAY_BETWEEN_REQUESTS)

        if idx % BATCH_SIZE == 0:
            save_results(results, run_id)
            print(f"\nSaved intermediate results ({len(results)} entries)")

    save_results(results, run_id)

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total custom cases tested: {len(results)}")
    print(f"Results saved to: retest_results_{run_id}.json")

    analyze_custom_results(results)


def _base_queries_by_subject(category: Optional[str], subject: Optional[str], procedure_name: str) -> List[str]:
    category = category or "unknown"
    subject = subject or "unknown"
    proc = procedure_name.strip()

    templates = {
        ("thong_tin_tong_quan", "thong_tin_lien_he"): [
            "dia chi ubnd xa ba diem",
            "so dien thoai ubnd xa ba diem",
        ],
        ("thong_tin_tong_quan", "lich_lam_viec"): [
            "ubnd xa lam viec tu may gio",
            "thu 7 ubnd co lam viec khong",
        ],
        ("to_chuc_bo_may", "nhan_su"): [
            "so dien thoai cua cong chuc tu phap ho tich",
            "ai phu trach bo phan mot cua",
        ],
        ("to_chuc_bo_may", "chuc_vu"): [
            "chuc vu cua can bo dia chinh la gi",
            "pho chu tich phu trach linh vuc nao",
        ],
    }

    if category == "thu_tuc_hanh_chinh":
        if proc:
            return [
                f"thu tuc {proc} can giay to gi",
                f"ho so {proc} gom nhung gi",
                f"le phi {proc} la bao nhieu",
            ]
        return [
            "thu tuc nay can giay to gi",
            "nop ho so o dau",
            "thoi gian giai quyet bao lau",
        ]

    if (category, subject) in templates:
        return templates[(category, subject)]

    if proc:
        return [
            f"thong tin ve {proc}",
            f"{proc} duoc giai quyet nhu the nao",
        ]

    if subject != "unknown":
        return [
            f"thong tin ve {subject}",
            f"hoi ve {subject} tai xa ba diem",
        ]

    return [
        "xin thong tin huong dan",
        "toi can duoc tu van ve thu tuc",
    ]


def _normalize_case_query(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _build_cases_from_chunks(chunks: List[Dict], max_cases: Optional[int], include_empty_subject: bool) -> List[Dict]:
    cases: List[Dict] = []
    seen_queries: Set[str] = set()
    index = 1

    for chunk in chunks:
        category = chunk.get("category")
        subject = chunk.get("subject")
        procedure_name = (chunk.get("procedure_name") or "").strip()

        if not category:
            continue
        if not include_empty_subject and not subject:
            continue

        candidate_queries = _base_queries_by_subject(category, subject, procedure_name)

        for query in candidate_queries:
            query = _normalize_case_query(query)
            if not query:
                continue
            if query in seen_queries:
                continue

            seen_queries.add(query)
            case_id = f"A{index:03d}"
            index += 1

            cases.append(
                {
                    "id": case_id,
                    "tag": subject or category,
                    "query": query,
                    "expected_category": category,
                    "expected_subject": subject,
                    "source": {
                        "chunk_id": chunk.get("id"),
                        "procedure_name": procedure_name or None,
                    },
                }
            )

            if max_cases and len(cases) >= max_cases:
                return cases

    return cases


def generate_cases_from_chunks(
    output_file: str,
    api_base_url: str,
    max_cases: Optional[int],
    include_empty_subject: bool,
) -> List[Dict]:
    chunks = fetch_chunks_from_api(api_base_url)

    cases = _build_cases_from_chunks(
        chunks=chunks,
        max_cases=max_cases,
        include_empty_subject=include_empty_subject,
    )

    output = {
        "generated_at": datetime.now().isoformat(),
        "source": f"{api_base_url}/api/get-chunks",
        "total_chunks": len(chunks),
        "total_cases": len(cases),
        "cases": cases,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("=" * 80)
    print("GENERATE CUSTOM CASES FROM CHUNKS")
    print("=" * 80)
    print(f"Loaded chunks: {len(chunks)}")
    print(f"Generated cases: {len(cases)}")
    print(f"Saved to: {output_file}")

    return cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retest classifier via /api/chat-stream")
    parser.add_argument(
        "legacy_max_queries",
        nargs="?",
        type=int,
        help="Optional max queries for backwards compatibility",
    )
    parser.add_argument(
        "--max-queries",
        type=int,
        default=None,
        help="Limit number of queries/cases to retest",
    )
    parser.add_argument(
        "--custom-file",
        type=str,
        default=None,
        help="Run against a custom regression JSON file",
    )
    parser.add_argument(
        "--api-base-url",
        type=str,
        default=API_BASE_URL,
        help="API base url, default: http://localhost:8001",
    )
    parser.add_argument(
        "--logs-file",
        type=str,
        default=DEFAULT_LOGS_FILE,
        help=f"Input logs file for run_retest, default: {DEFAULT_LOGS_FILE}",
    )
    parser.add_argument(
        "--generate-cases-from-chunks",
        action="store_true",
        help="Generate custom regression cases from /api/get-chunks",
    )
    parser.add_argument(
        "--cases-output",
        type=str,
        default=DEFAULT_CASES_OUTPUT,
        help=f"Output path for generated cases, default: {DEFAULT_CASES_OUTPUT}",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Maximum number of generated cases",
    )
    parser.add_argument(
        "--include-empty-subject",
        action="store_true",
        help="Include chunks with empty subject as expected_subject=null",
    )
    parser.add_argument(
        "--run-generated",
        action="store_true",
        help="Run custom retest immediately after generating cases",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    global API_BASE_URL
    API_BASE_URL = args.api_base_url

    max_queries = args.max_queries if args.max_queries is not None else args.legacy_max_queries

    if args.generate_cases_from_chunks:
        generate_cases_from_chunks(
            output_file=args.cases_output,
            api_base_url=API_BASE_URL,
            max_cases=args.max_cases,
            include_empty_subject=args.include_empty_subject,
        )
        if args.run_generated:
            run_custom_retest(args.cases_output, max_queries)
        return

    if args.custom_file:
        run_custom_retest(args.custom_file, max_queries)
    else:
        run_retest(max_queries, logs_file=args.logs_file)


if __name__ == "__main__":
    main()
