"""User-approved immutable valid-revision data domain and deterministic winner@2."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from random import Random
from typing import Any

CONTRACT = "sql.dedup.education_grade_revisions"
Tables = dict[str, list[dict[str, Any]]]
BEHAVIORS = ("valid", "cancelled_latest", "timestamp_tie", "exact_repeat", "cancelled_only",
             "multiple_students", "multiple_courses", "nonmonotone_id_time", "old_year_valid")


def revision(identifier: int, student: int = 1, course: int = 10, *,
             at: str = "2025-01-01 00:00:00", status: str = "valid", grade: str = "B") -> dict[str, Any]:
    return {"revision_id": identifier, "student_id": student, "course_id": course,
            "recorded_at": at, "revision_status": status, "grade": grade}


def rich_fixture() -> Tables:
    winner = revision(7, at="2025-02-01 00:00:00", grade="A+")
    return {"grade_revisions": [revision(20), revision(3, at="2025-02-01 00:00:00", grade="A"),
        winner, dict(winner), revision(30, at="2025-03-01 00:00:00", status="cancelled", grade="F"),
        revision(11, course=20, grade="C"), revision(12, course=20, at="2025-04-01 00:00:00", grade="C+"),
        revision(13, 2, grade="D"), revision(14, 3, status="cancelled", grade="E"),
        revision(15, 4, at="2024-12-31 00:00:00", grade="Old"),
        revision(16, 5, at="2026-01-01 00:00:00", grade="Future")]}


def alternatives(reference: str) -> list[str]:
    return [reference,
        ("SELECT DISTINCT r.student_id,r.course_id,r.grade,r.recorded_at,r.revision_id FROM grade_revisions r "
         "WHERE r.revision_status='valid' AND NOT EXISTS (SELECT 1 FROM grade_revisions newer "
         "WHERE newer.revision_status='valid' AND newer.student_id=r.student_id AND newer.course_id=r.course_id "
         "AND (newer.recorded_at,newer.revision_id)>(r.recorded_at,r.revision_id)) ORDER BY r.student_id,r.course_id"),
        ("WITH valid AS (SELECT * FROM grade_revisions WHERE revision_status='valid'), times AS "
         "(SELECT student_id,course_id,MAX(recorded_at) AS last_at FROM valid GROUP BY student_id,course_id), "
         "ids AS (SELECT v.student_id,v.course_id,MAX(v.revision_id) AS last_id FROM valid v "
         "JOIN times t ON t.student_id=v.student_id AND t.course_id=v.course_id AND t.last_at=v.recorded_at "
         "GROUP BY v.student_id,v.course_id) SELECT DISTINCT v.student_id,v.course_id,v.grade,v.recorded_at,v.revision_id "
         "FROM valid v JOIN times t ON t.student_id=v.student_id AND t.course_id=v.course_id AND t.last_at=v.recorded_at "
         "JOIN ids i ON i.student_id=v.student_id AND i.course_id=v.course_id AND i.last_id=v.revision_id "
         "ORDER BY v.student_id,v.course_id")]


def failures(reference: str) -> dict[str, str]:
    return {
        "all_statuses": reference.replace("revision_status = 'valid'", "TRUE"),
        "cancelled_only": reference.replace("revision_status = 'valid'", "revision_status = 'cancelled'"),
        "oldest_time": reference.replace("recorded_at DESC", "recorded_at ASC"),
        "smallest_tie": reference.replace("revision_id DESC", "revision_id ASC"),
        "id_before_time": reference.replace("recorded_at DESC, revision_id DESC", "revision_id DESC, recorded_at DESC"),
        "student_only": reference.replace("PARTITION BY student_id, course_id", "PARTITION BY student_id"),
        "course_only": reference.replace("PARTITION BY student_id, course_id", "PARTITION BY course_id"),
        "global_latest": reference.replace("PARTITION BY student_id, course_id", ""),
        "grade_partition": reference.replace("PARTITION BY student_id, course_id", "PARTITION BY student_id, course_id, grade"),
        "old_row_preference": reference.replace("recorded_at DESC, revision_id DESC", "recorded_at ASC, revision_id ASC"),
        "second_latest": reference.replace(") = 1", ") = 2"),
        "two_latest": reference.replace(") = 1", ") <= 2"),
        "all_rows": reference.replace(") = 1", ") >= 1"),
        "rank_repeats": reference.replace("ROW_NUMBER()", "RANK()"),
        "dense_rank_repeats": reference.replace("ROW_NUMBER()", "DENSE_RANK()"),
        "wrong_grade": reference.replace("course_id, grade,", "course_id, 'wrong' AS grade,"),
        "status_as_grade": reference.replace("course_id, grade,", "course_id, revision_status AS grade,"),
        "course_as_student": reference.replace("SELECT student_id,", "SELECT course_id AS student_id,"),
        "student_as_course": reference.replace("student_id, course_id, grade,", "student_id, student_id AS course_id, grade,"),
        "text_revision_id": reference.replace("recorded_at, revision_id FROM", "recorded_at, CAST(revision_id AS VARCHAR) AS revision_id FROM"),
        "reverse_student": reference.replace("ORDER BY student_id ASC", "ORDER BY student_id DESC"),
        "reverse_course": reference.replace("course_id ASC", "course_id DESC"),
        "year_filter_invented": reference.replace("WHERE revision_status", "WHERE EXTRACT(YEAR FROM recorded_at)=2025 AND revision_status"),
        "truncated_pairs": reference+" LIMIT 1",
    }


def proofs(reference: str) -> dict[str, Any]:
    wrong = failures(reference)
    keys = {"objective": "all_statuses", "duplicate_key": "student_only", "winner_rule": "oldest_time",
            "tie_break": "smallest_tie", "timestamp_tie_policy": "smallest_tie", "canceled_policy": "all_statuses",
            "no_valid_policy": "cancelled_only", "output_columns": "text_revision_id", "order_by": "reverse_course",
            "exact_repeats": "rank_repeats"}
    result = {key: {"witness": rich_fixture(), "wrong_sql": wrong[label], "outcome": "UNEXECUTED_RULE_SPEC"}
              for key, label in keys.items()}
    result["immutable_valid_revision_identity"] = {"witness": {"grade_revisions": [revision(1, grade="A"), revision(1, grade="B")]},
                                                   "outcome": "UNEXECUTED_DOMAIN_REJECTION_SPEC"}
    return result


def challenge_specs(reference: str) -> list[tuple[str, Tables]]:
    return [(wrong, rich_fixture()) for wrong in failures(reference).values()]


def relation_specs(reference: str) -> list[tuple[str, str, Tables]]:
    baseline = {"grade_revisions": [revision(1)]}
    wrong = failures(reference)
    return [("GRADE_VALID_REPEAT", wrong["rank_repeats"], baseline),
            ("GRADE_CANCELLED_LATEST", wrong["all_statuses"], baseline)]


def fixture(seed: int, index: int) -> Tables:
    rng = Random(f"grade-immutable:2:{seed}:{index}")
    tables = rich_fixture()
    for student in range(100, rng.randint(101, 116)):
        for course in rng.sample([100,101,102], rng.randrange(1,4)):
            for _ in range(rng.randrange(1,8)):
                at = datetime.fromisoformat("2024-12-01 00:00:00")+timedelta(days=rng.randrange(450))
                identifier = len(tables["grade_revisions"])+200
                tables["grade_revisions"].append(revision(identifier, student, course, at=at.isoformat(sep=" "),
                    grade=rng.choice(["A","B","C","D"]), status=rng.choice(["valid","cancelled"])))
    rng.shuffle(tables["grade_revisions"])
    return tables


def observed(tables: Tables) -> tuple[str, tuple[str, ...], set[str]]:
    found: set[str] = set()
    groups: dict[tuple[int,int],list[dict[str,Any]]] = {}
    for row in tables["grade_revisions"]:
        groups.setdefault((row["student_id"],row["course_id"]),[]).append(row)
        if row["revision_status"] == "valid":
            found.add("valid")
            if str(row["recorded_at"])[:4] < "2025":
                found.add("old_year_valid")
    for rows in groups.values():
        valid = [row for row in rows if row["revision_status"] == "valid"]
        if rows and not valid:
            found.add("cancelled_only")
        if valid:
            latest = max(valid,key=lambda row:(str(row["recorded_at"]),row["revision_id"]))
            if any(row["revision_status"] != "valid" and str(row["recorded_at"])>str(latest["recorded_at"]) for row in rows):
                found.add("cancelled_latest")
            if any(str(row["recorded_at"])==str(latest["recorded_at"]) and row["revision_id"]!=latest["revision_id"] for row in valid):
                found.add("timestamp_tie")
            if max(valid,key=lambda row:row["revision_id"])["revision_id"] != latest["revision_id"]:
                found.add("nonmonotone_id_time")
    if len({student for student,_ in groups})>1:
        found.add("multiple_students")
    if len({course for _,course in groups})>1:
        found.add("multiple_courses")
    if any(count>1 for count in Counter(tuple(sorted(row.items())) for row in tables["grade_revisions"]).values()):
        found.add("exact_repeat")
    return "grade-immutable-observed-v2", BEHAVIORS, found
