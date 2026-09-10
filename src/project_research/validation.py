"""Model assessments are inputs; evidence gates and decisions are Python rules."""

from dataclasses import asdict

from research_io import run_parallel

from . import prompts
from .config import ProjectConfig
from .evidence import independent_groups, make_evidence
from .schemas import (EvidencePack, EvidenceSelection, ProjectIdea, SCORE_LIMITS, ValidationDraft,
                      ValidationResult, validate_claims)
from .signals import canonical_url


def decide(idea: ProjectIdea, pack: EvidencePack, assessment: ValidationDraft,
           config: ProjectConfig) -> ValidationResult:
    if pack.idea_id != idea.id:
        raise ValueError("Evidence Pack belongs to another idea")
    docs = {d.id: d for d in pack.documents}
    for item in pack.items:
        rebuilt = make_evidence(EvidenceSelection(item.document_id, item.quote, item.finding, item.evidence_type), docs)
        if rebuilt != item:
            raise ValueError("Evidence provenance differs from its source document")
    if len({e.id for e in pack.items}) != len(pack.items):
        raise ValueError("Duplicate evidence IDs")
    groups = independent_groups(pack.items)
    # Never trust a cached or model-provided independent_evidence_count.
    pack.independent_groups, pack.independent_evidence_count = groups, len(groups)
    validate_claims(assessment, pack)
    scores = asdict(assessment.scores)
    for name, value in scores.items():
        if type(value) is not int or not 0 <= value <= SCORE_LIMITS[name]:
            raise ValueError(f"Score {name} must be an integer in [0,{SCORE_LIMITS[name]}]")
    if not assessment.next_validation_step.strip():
        raise ValueError("A next validation step is required")
    hard, missing = [], []
    if not idea.description.target_user.strip():
        hard.append("missing_target_user")
    if not groups:
        hard.append("zero_external_evidence")
    if not idea.description.differentiation_hypothesis.strip():
        hard.append("no_differentiation")
    if len(groups) < config.min_independent_evidence:
        missing.append(f"Need {config.min_independent_evidence} independent demand sources; found {len(groups)}")
    competitor_items = {e.id: e for e in pack.items if e.evidence_type == "competitor"}
    verified_competitors = []
    for competitor in assessment.competitors:
        urls = {canonical_url(e.url) for e in competitor_items.values()}
        if canonical_url(competitor.url) not in urls:
            raise ValueError("Competitor URL is not supported by competitor evidence")
        # A gap must be a supported finding, not a hypothesis that was relabeled by the writer.
        cited = [competitor_items[e] for e in competitor.gap.evidence_ids if e in competitor_items]
        if competitor.gap.kind != "HYPOTHESIS" and any(canonical_url(e.url) == canonical_url(competitor.url)
                                                       for e in cited):
            verified_competitors.append(competitor)
    if not verified_competitors:
        missing.append("Key competitor coverage/gap has not been verified")
    if any(error.startswith("Competitor fetch failed:") for error in pack.collection_errors):
        missing.append("A selected competitor page could not be verified")
    empirical = {"competitor_covers_problem", "dependency_unavailable", "license_disallows"}
    for rejection in assessment.rejections:
        if rejection.code in empirical:
            if rejection.reason.kind == "HYPOTHESIS" or not rejection.reason.evidence_ids:
                missing.append(f"Unverified rejection: {rejection.code}")
                continue
            if rejection.code == "competitor_covers_problem" and not (
                    set(rejection.reason.evidence_ids) & set(competitor_items)):
                missing.append("Competitor coverage rejection lacks competitor evidence")
                continue
        hard.append(rejection.code)
    if not idea.description.mvp:
        missing.append("MVP scope is missing")
    total = sum(scores.values())
    decision = ("REJECT" if hard or total < config.decision_thresholds.hold else
                "HOLD" if missing or total < config.decision_thresholds.go else "GO")
    return ValidationResult(idea.id, assessment, total, decision, sorted(set(hard)), missing)


def validate_ideas(ideas: list[ProjectIdea], packs: list[EvidencePack], config: ProjectConfig,
                   profile: str, ask) -> list[ValidationResult]:
    lookup = {p.idea_id: p for p in packs}
    def validate(idea: ProjectIdea) -> ValidationResult:
        pack = lookup[idea.id]
        assessment = ask("project_validator", prompts.prompt(prompts.VALIDATION_PROMPT,
                         idea=idea, evidence=pack, profile=profile, score_limits=SCORE_LIMITS,
                         thresholds=config.decision_thresholds), ValidationDraft)
        return decide(idea, pack, assessment, config)
    return run_parallel(validate, ideas, config.codex.max_concurrency)
