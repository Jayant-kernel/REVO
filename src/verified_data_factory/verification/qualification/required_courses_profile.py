"""Education required-course division@1: distinct courses, existential attempts."""
from __future__ import annotations

from collections import Counter, defaultdict
from random import Random
from typing import Any

CONTRACT = "sql.subqueries.education_all_required"
Tables = dict[str, list[dict[str, Any]]]
BEHAVIORS = ("qualified", "missing_course", "empty_program", "duplicate_requirement",
             "repeated_attempt", "mixed_pass_fail", "threshold_equal", "below_threshold",
             "null_score", "optional_course", "orphan_attempt", "student_bag", "multiple_programs")


def rich_fixture() -> Tables:
    students = [{"student_id": i, "program_id": 10 if i in (1, 2, 3, 5, 6) else 20 if i in (7, 8) else 30}
                for i in range(1, 9)]
    students.insert(0, dict(students[0]))
    attempts: list[dict[str, Any]] = []
    for owner, course, score in [(1, 10, 50), (1, 10, 0), (1, 10, 50), (1, 11, 70),
                                (1, 99, 100), (2, 10, 70), (2, 99, 100),
                                (3, 10, 70), (3, 11, 80), (5, 10, 70), (5, 10, 80),
                                (6, 10, 49), (6, 11, 100), (7, 20, 50), (7, 20, None),
                                (7, 20, 0), (8, 20, None), (99, 10, 100), (99, 11, 100), (3, 11, 0)]:
        attempts.append({"attempt_id": len(attempts)+1, "student_id": owner,
                         "course_id": course, "score": score})
    return {"students": students, "required_courses": [
                {"program_id": 10, "course_id": 10}, {"program_id": 10, "course_id": 10},
                {"program_id": 10, "course_id": 11}, {"program_id": 20, "course_id": 20}],
            "attempts": attempts}


def alternatives(reference: str) -> list[str]:
    required = "(SELECT COUNT(DISTINCT r.course_id) FROM required_courses r WHERE r.program_id=s.program_id)"
    return [reference,
        (f"SELECT s.student_id FROM students s WHERE {required}>0 AND {required}="
         "(SELECT COUNT(DISTINCT r.course_id) FROM required_courses r JOIN attempts a "
         "ON a.course_id=r.course_id AND a.student_id=s.student_id AND a.score>=50 "
         "WHERE r.program_id=s.program_id) ORDER BY s.student_id"),
        ("WITH passing AS (SELECT DISTINCT student_id,course_id FROM attempts WHERE score>=50) "
         "SELECT s.student_id FROM students s WHERE EXISTS "
         "(SELECT 1 FROM required_courses r WHERE r.program_id=s.program_id) AND NOT EXISTS "
         "(SELECT 1 FROM required_courses r WHERE r.program_id=s.program_id AND r.course_id NOT IN "
         "(SELECT p.course_id FROM passing p WHERE p.student_id=s.student_id)) ORDER BY s.student_id")]


def failures(reference: str) -> dict[str, str]:
    required = "(SELECT COUNT(DISTINCT r.course_id) FROM required_courses r WHERE r.program_id=s.program_id)"
    total = "(SELECT COUNT(DISTINCT a.course_id) FROM attempts a WHERE a.student_id=s.student_id AND a.score>=50)"
    counted = alternatives(reference)[1]
    return {
        "strict_threshold": reference.replace("a.score >= 50", "a.score > 50"),
        "threshold_49": reference.replace("a.score >= 50", "a.score >= 49"),
        "fail_only": reference.replace("a.score >= 50", "a.score < 50"),
        "equal_only": reference.replace("a.score >= 50", "a.score = 50"),
        "null_counts_as_pass": reference.replace("a.score >= 50", "(a.score >= 50 OR a.score IS NULL)"),
        "score_ignored": reference.replace("a.score >= 50", "TRUE"),
        "all_programs_required": reference.replace("r.program_id=s.program_id", "TRUE"),
        "other_program_required": reference.replace("r.program_id=s.program_id", "r.program_id<>s.program_id"),
        "owner_ignored": reference.replace("a.student_id=s.student_id", "TRUE"),
        "owner_wrong_key": reference.replace("a.student_id=s.student_id", "a.attempt_id=s.student_id"),
        "course_ignored": reference.replace("a.course_id=r.course_id", "TRUE"),
        "wrong_course_key": reference.replace("a.course_id=r.course_id", "a.course_id=r.program_id"),
        "vacuous_program_included": reference.replace("EXISTS (SELECT 1 FROM required_courses r WHERE r.program_id=s.program_id)", "TRUE"),
        "missing_course_selected": reference.replace("AND NOT EXISTS (SELECT 1 FROM required_courses", "AND EXISTS (SELECT 1 FROM required_courses"),
        "optional_replaces_required": f"SELECT s.student_id FROM students s WHERE {required}>0 AND {total}>={required} ORDER BY s.student_id",
        "optional_disqualifies": f"SELECT s.student_id FROM students s WHERE {required}>0 AND {total}={required} ORDER BY s.student_id",
        "failed_attempt_erases_pass": reference.replace("a.score >= 50", "a.score >= 50 AND NOT EXISTS "
            "(SELECT 1 FROM attempts bad WHERE bad.student_id=a.student_id AND bad.course_id=a.course_id AND bad.score<50)"),
        "latest_attempt_only": reference.replace("a.score >= 50", "a.score >= 50 AND a.attempt_id="
            "(SELECT MAX(last.attempt_id) FROM attempts last WHERE last.student_id=a.student_id AND last.course_id=a.course_id)"),
        "student_bag_collapsed": reference.replace("SELECT s.student_id", "SELECT DISTINCT s.student_id", 1),
        "id_as_text": reference.replace("SELECT s.student_id", "SELECT CAST(s.student_id AS VARCHAR) AS student_id", 1),
        "program_projected": reference.replace("SELECT s.student_id", "SELECT s.program_id AS student_id", 1),
        "reverse_order": reference + " DESC",
        "first_only": reference + " LIMIT 1",
        "raw_requirement_count": counted.replace("COUNT(DISTINCT r.course_id)", "COUNT(*)", 2),
        "attempt_fanout": counted.replace("SELECT COUNT(DISTINCT r.course_id) FROM required_courses r JOIN", "SELECT COUNT(*) FROM required_courses r JOIN"),
    }


def proofs(reference: str) -> dict[str, Any]:
    wrong = failures(reference)
    keys = {"objective": "course_ignored", "passing_score": "threshold_49",
            "year": "latest_attempt_only", "status_filter": "score_ignored",
            "threshold_operator": "strict_threshold", "exists_semantics": "attempt_fanout",
            "no_match_behavior": "vacuous_program_included", "output_columns": "id_as_text",
            "order_by": "reverse_order", "null_score": "null_counts_as_pass",
            "required_set": "raw_requirement_count", "failed_attempts": "failed_attempt_erases_pass",
            "optional_courses": "optional_replaces_required", "correlation": "owner_ignored",
            "student_bag": "student_bag_collapsed"}
    return {key: {"witness": rich_fixture(), "wrong_sql": wrong[label], "outcome": "UNEXECUTED_RULE_SPEC"}
            for key, label in keys.items()}


def challenge_specs(reference: str) -> list[tuple[str, Tables]]:
    return [(sql, rich_fixture()) for sql in failures(reference).values()]


def relation_specs(reference: str) -> list[tuple[str, str, Tables]]:
    baseline = {"students": [{"student_id": 1, "program_id": 10}],
                "required_courses": [{"program_id": 10, "course_id": 10}],
                "attempts": [{"attempt_id": 1, "student_id": 1, "course_id": 10, "score": 50}]}
    wrong = failures(reference)
    return [("REQUIRED_COURSE_DUPLICATE", wrong["raw_requirement_count"], baseline),
            ("REQUIRED_FAILED_ATTEMPT", wrong["failed_attempt_erases_pass"], baseline)]


def fixture(seed: int, index: int) -> Tables:
    rng = Random(f"education-required:1:{seed}:{index}")
    tables = rich_fixture()
    size = rng.randint(2, (8, 30, 90)[index % 3])
    for offset in range(size):
        owner = 1000+index*100+offset
        program = 1000+offset
        courses = list(range(2000+offset*10, 2000+offset*10+rng.randrange(6)))
        tables["students"].append({"student_id": owner, "program_id": program})
        if rng.randrange(4) == 0:
            tables["students"].append({"student_id": owner, "program_id": program})
        for course in courses:
            requirement = {"program_id": program, "course_id": course}
            tables["required_courses"].extend([dict(requirement) for _ in range(rng.randint(1, 3))])
        for course in [*courses, 9999]:
            for _ in range(rng.randrange(5)):
                tables["attempts"].append({"attempt_id": len(tables["attempts"])+1,
                    "student_id": owner, "course_id": course,
                    "score": rng.choice([None, -100, 0, 49, 50, 51, 100, 2147483647])})
    for rows in tables.values():
        rng.shuffle(rows)
    return tables


def observed(tables: Tables) -> tuple[str, tuple[str, ...], set[str]]:
    found: set[str] = set()
    required: dict[int, set[int]] = defaultdict(set)
    passed: dict[int, set[int]] = defaultdict(set)
    histories: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for row in tables["required_courses"]:
        required[row["program_id"]].add(row["course_id"])
    owners = {row["student_id"] for row in tables["students"]}
    for row in tables["attempts"]:
        score = row["score"]
        histories[row["student_id"],row["course_id"]].append(score)
        if row["student_id"] not in owners:
            found.add("orphan_attempt")
        if score is None:
            found.add("null_score")
        else:
            if score == 50:
                found.add("threshold_equal")
            if score < 50:
                found.add("below_threshold")
            if score >= 50:
                passed[row["student_id"]].add(row["course_id"])
    for scores in histories.values():
        if len(scores) > 1:
            found.add("repeated_attempt")
        if any(score is not None and score >= 50 for score in scores) and any(score is not None and score < 50 for score in scores):
            found.add("mixed_pass_fail")
    for student in tables["students"]:
        courses = required[student["program_id"]]
        if not courses:
            found.add("empty_program")
        elif courses <= passed[student["student_id"]]:
            found.add("qualified")
        else:
            found.add("missing_course")
        if any(row["student_id"] == student["student_id"] and row["course_id"] not in courses
               for row in tables["attempts"]):
            found.add("optional_course")
    for name, behavior in (("students", "student_bag"), ("required_courses", "duplicate_requirement")):
        if any(count > 1 for count in Counter(tuple(sorted(row.items())) for row in tables[name]).values()):
            found.add(behavior)
    if len({row["program_id"] for row in tables["students"]}) > 1:
        found.add("multiple_programs")
    return "required-courses-observed-v1", BEHAVIORS, found
