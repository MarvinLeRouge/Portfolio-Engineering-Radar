from radar_core.enums import (
    Confidence,
    EvidenceType,
    FindingSeverity,
    FindingStatus,
    HumanVerdict,
    RoadmapStatus,
    ScoreLevel,
    ScoringModel,
)


def test_confidence_members():
    assert {c.value for c in Confidence} == {"HIGH", "MEDIUM", "LOW"}


def test_human_verdict_members():
    assert {v.value for v in HumanVerdict} == {
        "UNREVIEWED",
        "TRUE_POSITIVE",
        "FALSE_POSITIVE",
    }


def test_score_level_members():
    assert {level.value for level in ScoreLevel} == {"CRITERION", "CATEGORY", "GLOBAL"}


def test_scoring_model_members():
    assert {m.value for m in ScoringModel} == {"FIXED_SCALE", "STATUS_4STATE"}


def test_finding_severity_members():
    assert {s.value for s in FindingSeverity} == {
        "CRITICAL",
        "HIGH",
        "MEDIUM",
        "LOW",
        "INFO",
    }


def test_finding_status_members():
    assert {s.value for s in FindingStatus} == {"OPEN", "RESOLVED", "WONT_FIX"}


def test_evidence_type_members():
    assert {t.value for t in EvidenceType} == {
        "TOOL_OUTPUT_EXCERPT",
        "HUMAN_CONFIRMATION",
        "EXTERNAL_REFERENCE",
    }


def test_roadmap_status_members():
    assert {s.value for s in RoadmapStatus} == {"TODO", "IN_PROGRESS", "DONE", "WONT_FIX"}
