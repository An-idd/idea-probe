"""Typed artifacts and strict JSON boundaries, using only the standard library."""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any, Literal, TypeVar, get_args, get_origin, get_type_hints

T = TypeVar("T")
Decision = Literal["GO", "HOLD", "REJECT"]
Kind = Literal["FACT", "INFERENCE", "HYPOTHESIS"]


def stable_id(prefix: str, *parts: str) -> str:
    return prefix + "_" + hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:20]


def decode(cls: type[T], value: object, path: str = "result") -> T:
    """Reject extra fields, bool-as-int and malformed nested values at all JSON boundaries."""
    if cls is Any:
        return value
    origin, args = get_origin(cls), get_args(cls)
    if origin is Literal:
        if value not in args or not isinstance(value, str):
            raise ValueError(f"{path}: expected one of {args}")
    elif origin is list:
        if not isinstance(value, list):
            raise ValueError(f"{path}: expected list")
        return [decode(args[0], item, f"{path}[{i}]") for i, item in enumerate(value)]
    elif origin is dict:
        if not isinstance(value, dict):
            raise ValueError(f"{path}: expected object")
        return {decode(args[0], k, path): decode(args[1], v, f"{path}.{k}") for k, v in value.items()}
    elif is_dataclass(cls):
        if not isinstance(value, dict):
            raise ValueError(f"{path}: expected object")
        hints = get_type_hints(cls)
        if set(value) - set(hints):
            raise ValueError(f"{path}: unexpected fields {sorted(set(value) - set(hints))}")
        try:
            return cls(**{k: decode(hints[k], v, f"{path}.{k}") for k, v in value.items()})
        except TypeError as exc:
            raise ValueError(f"{path}: missing required fields") from exc
    elif cls is float:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"{path}: expected finite number")
        return float(value)
    elif type(value) is not cls:
        raise ValueError(f"{path}: expected {cls.__name__}")
    return value


def json_schema(cls: type) -> dict:
    """The same dataclasses define Codex's output contract and Python's decoder."""
    origin, args = get_origin(cls), get_args(cls)
    if origin is Literal:
        return {"type": "string", "enum": list(args)}
    if origin is list:
        return {"type": "array", "items": json_schema(args[0])}
    if is_dataclass(cls):
        props = {f.name: json_schema(get_type_hints(cls)[f.name]) for f in fields(cls)}
        if cls is Claim:
            props["evidence_ids"]["description"] = (
                "Use only IDs from EvidencePack.items[].id, never document_id/doc_, signal_id/sig_, or URLs. "
                "An unsupported HYPOTHESIS should use an empty list.")
            props["evidence_ids"]["items"]["pattern"] = r"^ev_[0-9a-f]{20}$"
        if cls is Competitor:
            props["url"]["description"] = (
                "Copy the exact URL of an EvidencePack.items entry whose evidence_type is competitor. "
                "When the evidence is an HN/Reddit post, use that post's URL, not the product homepage. "
                "Do not substitute a URL found inside document text or a failed-fetch URL.")
        return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}
    return {"type": {str: "string", int: "integer", float: "number", bool: "boolean"}[cls]}


@dataclass
class Document:
    id: str
    signal_id: str
    source: str
    url: str
    text: str
    thread: str
    author: str = ""
    repository: str = ""
    retrieved_at: str = ""
    source_type: str = "community"


@dataclass
class Signal:
    id: str
    source: str
    source_type: str
    title: str
    url: str
    summary: str
    author: str = ""
    published_at: str = ""
    metrics: dict[str, int] = field(default_factory=dict)
    repository: dict[str, Any] = field(default_factory=dict)
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    documents: list[Document] = field(default_factory=list)
    related_urls: list[str] = field(default_factory=list)


@dataclass
class ScreenResult:
    signal_ids: list[str]


@dataclass
class Observation:
    document_id: str
    quote: str
    finding: str


@dataclass
class ProblemDraft:
    problem: str
    target_user: str
    current_solution: str
    pain: str
    workaround: str
    desired_outcome: str
    confidence: float
    observations: list[Observation]


@dataclass
class ExtractResult:
    problems: list[ProblemDraft]


@dataclass
class Problem:
    id: str
    description: ProblemDraft
    source_signal_ids: list[str]
    observations: list[Observation]
    claim_status: Literal["INFERENCE"] = "INFERENCE"


@dataclass
class MergeGroup:
    ids: list[str]


@dataclass
class MergeResult:
    groups: list[MergeGroup]


@dataclass
class IdeaDraft:
    name: str
    one_liner: str
    problem_ids: list[str]
    target_user: str
    current_solution: str
    proposed_solution: str
    why_now: str
    differentiation_hypothesis: str
    mvp: list[str]
    non_goals: list[str]
    competitor_urls: list[str]


@dataclass
class IdeationResult:
    ideas: list[IdeaDraft]


@dataclass
class ProjectIdea:
    id: str
    description: IdeaDraft
    source_signal_ids: list[str]
    claim_status: Literal["HYPOTHESIS"] = "HYPOTHESIS"


@dataclass
class EvidenceSelection:
    document_id: str
    quote: str
    finding: str
    evidence_type: Literal["problem", "competitor", "provenance"]


@dataclass
class EvidenceSelections:
    items: list[EvidenceSelection]


@dataclass
class Evidence:
    id: str
    source: str
    url: str
    finding: str
    evidence_type: Literal["problem", "competitor", "provenance"]
    quote: str
    document_id: str
    signal_id: str
    thread: str
    author: str
    repository: str
    finding_kind: Literal["INFERENCE"] = "INFERENCE"


@dataclass
class Claim:
    text: str
    kind: Kind
    evidence_ids: list[str]


@dataclass
class Competitor:
    name: str
    url: str
    strengths: list[Claim]
    weaknesses: list[Claim]
    overlap: Claim
    gap: Claim


@dataclass
class EvidencePack:
    idea_id: str
    items: list[Evidence]
    documents: list[Document]
    independent_evidence_count: int
    independent_groups: list[list[str]]
    collection_errors: list[str]


@dataclass
class ScoreCard:
    problem_reality: int
    evidence_strength: int
    competitor_gap: int
    differentiation: int
    feasibility: int
    mvp_clarity: int
    distribution: int
    maintenance: int


SCORE_LIMITS = dict(zip(get_type_hints(ScoreCard), (20, 20, 15, 15, 10, 10, 5, 5)))


@dataclass
class Rejection:
    code: Literal["no_differentiation", "wrapper_only", "competitor_covers_problem", "outside_constraints",
                  "dependency_unavailable", "license_disallows", "model_only_difference"]
    reason: Claim


@dataclass
class ValidationDraft:
    scores: ScoreCard
    reasons: list[Claim]
    competitors: list[Competitor]
    rejections: list[Rejection]
    next_validation_step: str


@dataclass
class ValidationResult:
    idea_id: str
    assessment: ValidationDraft
    score: int
    decision: Decision
    hard_rejects: list[str]
    missing_evidence: list[str]


@dataclass
class RedTeamResult:
    verdict: Literal["PASS", "HOLD", "REJECT"]
    fatal_flaws: list[Claim]
    major_risks: list[Claim]
    missing_evidence: list[str]
    counter_arguments: list[Claim]


@dataclass
class RedTeamRecord:
    idea_id: str
    result: RedTeamResult


@dataclass
class BriefNarrative:
    technical_feasibility: Claim
    distribution: Claim
    risks: list[Claim]
    next_validation_step: str


@dataclass
class ProjectBrief:
    idea: ProjectIdea
    problems: list[Problem]
    evidence: EvidencePack
    validation: ValidationResult
    red_team: list[RedTeamResult]
    red_team_status: Literal["completed", "disabled", "not_selected"]
    narrative: BriefNarrative
    final_decision: Decision


@dataclass
class RunState:
    id: str
    started_at: str
    fingerprint: str
    config: dict[str, Any]
    status: str = "running"
    completed_stages: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    artifact_hashes: dict[str, str] = field(default_factory=dict)
    model_calls: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""


def validate_claims(value: object, pack: EvidencePack) -> None:
    """A cited claim must name available evidence; an uncited statement is a hypothesis."""
    known = {e.id for e in pack.items}
    if isinstance(value, Claim):
        if not value.text.strip():
            raise ValueError("Empty claim")
        if set(value.evidence_ids) - known:
            raise ValueError("Claim cites unknown evidence")
        if value.kind != "HYPOTHESIS" and not value.evidence_ids:
            raise ValueError("FACT/INFERENCE requires evidence; use HYPOTHESIS for unsupported claims")
    elif is_dataclass(value):
        for f in fields(value):
            validate_claims(getattr(value, f.name), pack)
    elif isinstance(value, list):
        for item in value:
            validate_claims(item, pack)


def payload(value: object) -> object:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [payload(item) for item in value]
    return value
