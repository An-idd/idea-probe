"""Render authoritative decisions and cited evidence; model prose cannot change them."""

from research_io import run_parallel

from . import prompts
from .config import ProjectConfig
from .schemas import (BriefNarrative, Claim, Decision, EvidencePack, Problem, ProjectBrief, ProjectIdea,
                      RedTeamRecord, ValidationResult, validate_claims)


def final_decision(validation: ValidationResult, reviews: list[RedTeamRecord]) -> Decision:
    if validation.hard_rejects:
        return "REJECT"
    severity = {"GO": 0, "HOLD": 1, "REJECT": 2}
    decision = validation.decision
    for review in reviews:
        if review.idea_id == validation.idea_id:
            verdict = "REJECT" if review.result.fatal_flaws else review.result.verdict
            if verdict != "PASS" and severity[verdict] > severity[decision]:
                decision = verdict
    return decision


def generate_briefs(ranked: list[ValidationResult], ideas: list[ProjectIdea], problems: list[Problem],
                     packs: list[EvidencePack], reviews: list[RedTeamRecord], config: ProjectConfig,
                     ask) -> list[ProjectBrief]:
    idea_map, pack_map = {i.id: i for i in ideas}, {p.idea_id: p for p in packs}
    def write(validation: ValidationResult) -> ProjectBrief:
        idea, pack = idea_map[validation.idea_id], pack_map[validation.idea_id]
        selected_problems = [p for p in problems if p.id in idea.description.problem_ids]
        result = ask("project_brief_writer", prompts.prompt(prompts.BRIEF_PROMPT,
                     idea=idea, problems=selected_problems, evidence=pack, validation=validation), BriefNarrative)
        validate_claims(result, pack)
        if not result.next_validation_step.strip():
            raise ValueError("Brief needs a next validation step")
        red = [r.result for r in reviews if r.idea_id == idea.id]
        status = "completed" if red else "not_selected" if config.red_team.enabled else "disabled"
        return ProjectBrief(idea, selected_problems, pack, validation, red, status, result,
                            final_decision(validation, reviews))
    return run_parallel(write, ranked[:config.top_k], config.codex.max_concurrency)


def render_markdown(brief: ProjectBrief) -> str:
    import html
    from dataclasses import asdict
    from .schemas import SCORE_LIMITS
    def escape(value: str) -> str:
        return html.escape(value).replace("|", "\\|").replace("\n", " ")

    evidence = {e.id: e for e in brief.evidence.items}
    def claim(value: Claim) -> str:
        links = " ".join(f"[{key}]({evidence[key].url})" for key in value.evidence_ids)
        return f"[{value.kind}] {escape(value.text)} {links}".rstrip()

    def bullets(values: list[str]) -> str:
        return "\n".join("- " + escape(v) for v in values) or "None recorded."

    idea = brief.idea.description
    sections = ["# Project Research Brief",
                "## Project\n\n" + escape(idea.name) + "\n\n" + escape(idea.one_liner)
                + f"\n\nDecision: **{brief.final_decision}**\n\nScore: **{brief.validation.score}/100**",
                "## Target User\n\n" + escape(idea.target_user),
                "## Problem\n\n" + bullets([p.description.problem for p in brief.problems]),
                "## Problem Evidence\n\nIndependent evidence count: "
                + str(brief.evidence.independent_evidence_count)]
    for entry in brief.evidence.items:
        sections.append(f"### {entry.id} ({entry.evidence_type})\n\nSource: {escape(entry.source)}"
                        f"\n\nURL: [source]({entry.url})\n\nQuote: {escape(entry.quote)}"
                        f"\n\nFinding (source-grounded summary): {escape(entry.finding)}")
    sections += ["## Current Solutions\n\n[HYPOTHESIS — user workflow summary] " + escape(idea.current_solution),
                 "## Competitors"]
    for competitor in brief.validation.assessment.competitors:
        sections.append(f"### {escape(competitor.name)}\n\n[Source]({competitor.url})\n\n"
                        + "\n\n".join(["Strength: " + claim(c) for c in competitor.strengths]
                                        + ["Weakness: " + claim(c) for c in competitor.weaknesses]
                                        + ["Overlap: " + claim(competitor.overlap), "Gap: " + claim(competitor.gap)]))
    if not brief.validation.assessment.competitors:
        sections.append("Competitor coverage is unverified; no absence claim is made.")
    sections += ["## Proposed Solution\n\n[HYPOTHESIS] " + escape(idea.proposed_solution),
                 "## Differentiation\n\n[HYPOTHESIS] " + escape(idea.differentiation_hypothesis),
                 "## Why Now\n\n[HYPOTHESIS] " + escape(idea.why_now),
                 "## MVP\n\n" + bullets(idea.mvp), "## Non-goals\n\n" + bullets(idea.non_goals),
                 "## Technical Feasibility\n\n" + claim(brief.narrative.technical_feasibility),
                 "## Distribution\n\n" + claim(brief.narrative.distribution),
                 "## Risks\n\n" + ("\n\n".join(claim(c) for c in brief.narrative.risks) or "None recorded."),
                 "## Red Team\n\nStatus: " + brief.red_team_status]
    for review in brief.red_team:
        sections.append("Verdict: " + review.verdict + "\n\nFatal flaws:\n\n"
                        + ("\n\n".join(claim(c) for c in review.fatal_flaws) or "None recorded.")
                        + "\n\nMajor risks:\n\n"
                        + ("\n\n".join(claim(c) for c in review.major_risks) or "None recorded.")
                        + "\n\nMissing evidence:\n\n" + bullets(review.missing_evidence)
                        + "\n\nCounter arguments:\n\n"
                        + ("\n\n".join(claim(c) for c in review.counter_arguments) or "None recorded."))
    sections += ["## Final Decision\n\n**" + brief.final_decision + "**\n\n"
                 + bullets(brief.validation.hard_rejects + brief.validation.missing_evidence)
                 + "\n\n" + "\n\n".join(claim(c) for c in brief.validation.assessment.reasons),
                 "## Next Validation Step\n\n" + escape(brief.narrative.next_validation_step),
                 "## Provenance\n\nIdea: " + brief.idea.id + "\n\nProblems: "
                 + ", ".join(p.id for p in brief.problems) + "\n\nOrigin signals: "
                 + ", ".join(brief.idea.source_signal_ids),
                 "## Collection Gaps\n\n" + bullets(brief.evidence.collection_errors)]
    sections.append("## Validation Scores\n\n| Dimension | Score | Maximum |\n|---|---:|---:|\n"
                    + "\n".join(f"| {name} | {value} | {SCORE_LIMITS[name]} |"
                                for name, value in asdict(brief.validation.assessment.scores).items()))
    return "\n\n".join(sections) + "\n"
