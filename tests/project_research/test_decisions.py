from copy import deepcopy
from dataclasses import asdict, replace

import pytest

import research_fixtures

from project_research.brief import final_decision
from project_research.config import load_project_config
from project_research.evidence import independent_groups, make_evidence
from project_research.schemas import (Claim, EvidenceSelection, RedTeamRecord, RedTeamResult, Rejection,
                                      SCORE_LIMITS, decode, json_schema)
from project_research.validation import decide

case = research_fixtures.case
scenario = research_fixtures.scenario


def test_no_evidence_no_go(case):
    scenario, idea, _, pack, assessment = case
    pack.items = []
    pack.independent_evidence_count = 999
    assessment.competitors = []
    assessment.reasons = []
    result = decide(idea, pack, assessment, scenario.config)
    assert result.score == 100
    assert result.decision == "REJECT"
    assert "zero_external_evidence" in result.hard_rejects
    assert pack.independent_evidence_count == 0


def test_duplicate_evidence(case):
    _, _, _, pack, _ = case
    first = next(e for e in pack.items if e.evidence_type == "problem")
    comments = [replace(first, id=str(i), author=str(i), quote=f"different quote {i}") for i in range(20)]
    assert len(independent_groups(comments)) == 1


def test_independence_handles_author_repository_and_transitive_bridges(case):
    _, _, _, pack, _ = case
    first = next(e for e in pack.items if e.evidence_type == "problem")
    a = replace(first, id="a", thread="a", author="a", quote="a")
    b = replace(first, id="b", thread="b", author="b", quote="b", repository="repo")
    bridge = replace(first, id="c", thread="c", author="a", quote="c", repository="repo")
    assert independent_groups([a, b, bridge]) == [["a", "b", "c"]]


@pytest.mark.parametrize("code", ["no_differentiation", "wrapper_only", "competitor_covers_problem",
                                 "outside_constraints", "dependency_unavailable", "license_disallows",
                                 "model_only_difference"])
def test_hard_reject(case, code):
    scenario, idea, _, pack, assessment = case
    fact = assessment.reasons[0]
    assessment.rejections = [Rejection(code, fact)]
    result = decide(idea, pack, assessment, scenario.config)
    reviews = [RedTeamRecord(idea.id, RedTeamResult("PASS", [], [], [], []))]
    assert result.decision == final_decision(result, reviews) == "REJECT"
    assert code in result.hard_rejects


@pytest.mark.parametrize("score,expected", [(59, "REJECT"), (60, "HOLD"), (74, "HOLD"), (75, "GO"), (100, "GO")])
def test_thresholds(case, score, expected):
    scenario, idea, _, pack, assessment = case
    remaining = score
    for name, cap in SCORE_LIMITS.items():
        setattr(assessment.scores, name, min(remaining, cap))
        remaining -= min(remaining, cap)
    assert decide(idea, pack, assessment, scenario.config).decision == expected


def test_insufficient_evidence_and_unknown_competitors_hold(case):
    scenario, idea, _, pack, assessment = case
    scenario.config.min_independent_evidence = 3
    assert decide(idea, pack, assessment, scenario.config).decision == "HOLD"
    scenario.config.min_independent_evidence = 2
    assessment.competitors = []
    assert decide(idea, pack, assessment, scenario.config).decision == "HOLD"


def test_no_target_user_is_rejected(case):
    scenario, idea, _, pack, assessment = case
    idea.description.target_user = " "
    assert "missing_target_user" in decide(idea, pack, assessment, scenario.config).hard_rejects


def test_fabricated_quote_provenance_and_citation_fail(case):
    scenario, idea, _, pack, assessment = case
    with pytest.raises(ValueError, match="exact quote"):
        make_evidence(EvidenceSelection(pack.documents[0].id, "invented", "invented", "problem"),
                      {d.id: d for d in pack.documents})
    broken = deepcopy(pack)
    broken.items[0].url = "https://example.org/invented"
    with pytest.raises(ValueError, match="provenance"):
        decide(idea, broken, assessment, scenario.config)
    assessment.reasons = [Claim("Invented evidence", "FACT", ["missing"])]
    with pytest.raises(ValueError, match="unknown evidence"):
        decide(idea, pack, assessment, scenario.config)
    assessment.reasons = [Claim("Unsupported fact", "FACT", [])]
    with pytest.raises(ValueError, match="requires evidence"):
        decide(idea, pack, assessment, scenario.config)


def test_competitor_page_is_not_demand(case):
    _, _, _, pack, _ = case
    doc = next(d for d in pack.documents if d.source == "competitor_page")
    with pytest.raises(ValueError, match="do not establish"):
        make_evidence(EvidenceSelection(doc.id, doc.text, "demand", "problem"), {doc.id: doc})


def test_schemas_roundtrip_and_reject_invalid_numbers(case):
    _, idea, problems, pack, assessment = case
    for item in [idea, *problems, pack, assessment, *pack.documents, *pack.items]:
        assert decode(type(item), asdict(item)) == item
    raw = asdict(assessment)
    raw["scores"]["problem_reality"] = True
    with pytest.raises(ValueError, match="expected int"):
        decode(type(assessment), raw)
    raw = asdict(assessment)
    raw["extra"] = "ignored?"
    with pytest.raises(ValueError, match="unexpected fields"):
        decode(type(assessment), raw)
    schema = json_schema(type(assessment))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


def test_partial_configuration_and_invalid_values():
    config = load_project_config({"red_team": {"enabled": False}, "codex": {"models": ["my-local-model"]}})
    assert not config.red_team.enabled and config.red_team.top_k == 3
    assert config.codex.timeout_seconds == 300
    for invalid in ({"max_ideas": True}, {"top_k": -1}, {"codex": {"attempts": 0}},
                    {"decision_thresholds": {"go": 50, "hold": 70}}):
        with pytest.raises(ValueError):
            load_project_config(invalid)


def test_evidence_budget_and_competitor_failure(case):
    from project_research.evidence import collect_evidence
    scenario, idea, problems, _, assessment = case
    scenario.config.max_evidence_documents = 1
    pack = collect_evidence([idea], problems, scenario.signals, scenario.config,
                            scenario.ask, scenario.provider)[0]
    assert pack.independent_evidence_count == 0
    assert any("1/3" in gap for gap in pack.collection_errors)
    assert len(pack.items) >= 2  # Original provenance survives retrieval truncation.
    assert decide(idea, pack, assessment, scenario.config).decision == "REJECT"


def test_unknown_empirical_rejection_is_hold(case):
    scenario, idea, _, pack, assessment = case
    assessment.rejections = [Rejection("license_disallows", Claim("License needs checking", "HYPOTHESIS", []))]
    result = decide(idea, pack, assessment, scenario.config)
    assert result.decision == "HOLD" and not result.hard_rejects


def test_claim_output_schema_distinguishes_evidence_from_document_ids():
    import re
    from project_research.schemas import Claim, json_schema
    pattern = json_schema(Claim)["properties"]["evidence_ids"]["items"]["pattern"]
    assert re.fullmatch(pattern, "ev_0123456789abcdef0123")
    assert not re.fullmatch(pattern, "doc_0123456789abcdef0123")
