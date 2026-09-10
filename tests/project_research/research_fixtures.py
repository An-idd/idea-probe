"""Synthetic fixtures imported explicitly, preserving the old tests' conftest module."""

import json
from dataclasses import asdict

import pytest

from project_research.config import ProjectConfig
from project_research.schemas import (
    BriefNarrative, Claim, Competitor, EvidenceSelections, ExtractResult, IdeationResult, MergeResult,
    RedTeamResult, SCORE_LIMITS, ScoreCard, ScreenResult, Signal, ValidationDraft, decode,
)
from project_research.signals import document


def card(total=100):
    values = {}
    for key, cap in SCORE_LIMITS.items():
        values[key] = min(cap, total)
        total -= values[key]
    return ScoreCard(**values)


class Scenario:
    def __init__(self):
        self.config = ProjectConfig()
        self.config.max_competitor_pages = 1
        self.calls = []
        self.fail_red = False
        self.signals = []
        quotes = ("I cannot replay failed tool calls.", "Our team manually reconstructs tool inputs.")
        for number, text in enumerate(quotes):
            item = Signal(f"sig{number}", "reddit_python", "community", f"Replay issue {number}",
                          f"https://www.reddit.com/r/python/comments/thread{number}/topic", text,
                          author=f"author{number}")
            item.documents = [document(item, text)]
            self.signals.append(item)

    def provider(self, url, idea, config):
        item = Signal(idea.source_signal_ids[0], "competitor_page", "web", "Tool logger", url,
                      "Tool logger records calls. It does not support replay.")
        return document(item, item.summary)

    def ask(self, role, text, cls):
        data = json.loads(text.split("INPUT_DATA\n")[1])
        self.calls.append((role, cls))
        if cls is ScreenResult:
            return ScreenResult([s["id"] for s in data["signals"]])
        if cls is ExtractResult:
            return decode(cls, {"problems": [dict(
                problem="Failed calls cannot be replayed", target_user="Agent developers", current_solution="Logs",
                pain="Manual reconstruction", workaround="Copy inputs", desired_outcome="Replay a failed call",
                confidence=0.8, observations=[dict(document_id=s["documents"][0]["id"],
                                                 quote=s["documents"][0]["text"], finding="Manual debugging pain")])
                for s in data["signals"]]})
        if cls is MergeResult:
            return decode(cls, {"groups": [{"ids": [item["id"] for item in data["items"]]}]})
        if cls is IdeationResult:
            return decode(cls, {"ideas": [dict(
                name="Tool Replay", one_liner="Reproduce failed tool calls",
                problem_ids=[p["id"] for p in data["problems"]],
                target_user="Agent developers", current_solution="Manual logs",
                proposed_solution="Replay captured inputs",
                why_now="HYPOTHESIS: more complex agents", differentiation_hypothesis="Deterministic replay",
                mvp=["Capture", "Replay"], non_goals=["Agent platform"],
                competitor_urls=["https://example.org/tool-logger"])]})
        if cls is EvidenceSelections:
            return decode(cls, {"items": [dict(
                document_id=d["id"], quote=d["text"], finding=d["text"],
                evidence_type="competitor" if d["source"] == "competitor_page" else "problem")
                for d in data["documents"]]})
        if cls is ValidationDraft:
            items = data["evidence"]["items"]
            competitor = next(e for e in items if e["evidence_type"] == "competitor")
            fact = Claim("The tool has no replay feature", "FACT", [competitor["id"]])
            competitors = [Competitor("Tool logger", competitor["url"], [fact], [fact], fact, fact)]
            return ValidationDraft(card(), [fact], competitors, [], "Ask users to try replay")
        if cls is RedTeamResult:
            if self.fail_red:
                raise RuntimeError("red team unavailable")
            return RedTeamResult("PASS", [], [], [], [])
        if cls is BriefNarrative:
            hypothesis = Claim("A small CLI can be validated with early users", "HYPOTHESIS", [])
            return BriefNarrative(hypothesis, hypothesis, [], "Ask users to try replay")
        raise AssertionError(cls)


@pytest.fixture
def scenario(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "get", lambda *a, **k: pytest.fail("Unexpected network access"))
    return Scenario()


@pytest.fixture
def case(scenario):
    from project_research import ideation, evidence
    problems = ideation.extract_problems(scenario.signals, scenario.config, scenario.ask)
    problems = ideation.deduplicate_problems(problems, scenario.config, scenario.ask)
    ideas = ideation.generate_project_ideas(problems, scenario.config, "", "", scenario.ask)
    packs = evidence.collect_evidence(ideas, problems, scenario.signals, scenario.config,
                                      scenario.ask, scenario.provider)
    assessment = scenario.ask("project_validator", "INPUT_DATA\n" + json.dumps({"evidence": asdict(packs[0])}),
                              ValidationDraft)
    return scenario, ideas[0], problems, packs[0], assessment
