"""Optional top-K challenge, without the academic multi-model review machinery."""

from research_io import run_parallel

from . import prompts
from .config import ProjectConfig
from .schemas import (EvidencePack, ProjectIdea, RedTeamRecord, RedTeamResult, ValidationResult, validate_claims)


def red_team_top_k(ranked: list[ValidationResult], ideas: list[ProjectIdea], packs: list[EvidencePack],
                   config: ProjectConfig, ask) -> list[RedTeamRecord]:
    if not config.red_team.enabled:
        return []
    idea_map, pack_map = {i.id: i for i in ideas}, {p.idea_id: p for p in packs}
    def review(validation: ValidationResult) -> RedTeamRecord:
        pack = pack_map[validation.idea_id]
        result = ask("project_red_team", prompts.prompt(prompts.RED_TEAM_PROMPT,
                     idea=idea_map[validation.idea_id], evidence=pack, validation=validation), RedTeamResult)
        validate_claims(result, pack)
        if result.fatal_flaws:
            result.verdict = "REJECT"
        elif result.missing_evidence and result.verdict == "PASS":
            result.verdict = "HOLD"
        return RedTeamRecord(validation.idea_id, result)
    return run_parallel(review, ranked[:config.red_team.top_k], config.codex.max_concurrency)
