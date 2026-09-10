"""Screen, extract and merge while keeping source references intact."""

from dataclasses import replace

from . import prompts
from .config import ProjectConfig
from .schemas import (ExtractResult, IdeationResult, MergeResult, Problem, ProjectIdea, ScreenResult,
                      Signal, stable_id)


def batches(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def screen_opportunities(signals: list[Signal], config: ProjectConfig, ask) -> list[Signal]:
    selected = set()
    for batch in batches(signals, config.batch_size):
        result = ask("project_ideator", prompts.prompt(prompts.OPPORTUNITY_SCREEN_PROMPT,
                     topic=config.topic, signals=batch), ScreenResult)
        if set(result.signal_ids) - {s.id for s in batch}:
            raise ValueError("Screen returned unknown signal IDs")
        selected.update(result.signal_ids)
    return [s for s in signals if s.id in selected]


def extract_problems(signals: list[Signal], config: ProjectConfig, ask) -> list[Problem]:
    problems = []
    for batch in batches(signals, config.batch_size):
        docs = {d.id: d for s in batch for d in s.documents}
        result = ask("project_ideator", prompts.prompt(prompts.PROBLEM_EXTRACTION_PROMPT,
                     topic=config.topic, signals=batch), ExtractResult)
        for draft in result.problems:
            if not draft.problem.strip() or not 0 <= draft.confidence <= 1 or not draft.observations:
                raise ValueError("A problem needs a description, observations and confidence in [0,1]")
            for obs in draft.observations:
                if obs.document_id not in docs or not obs.quote.strip() or obs.quote not in docs[obs.document_id].text:
                    raise ValueError("Problem observation is not an exact quote from a known document")
            source_ids = sorted({docs[o.document_id].signal_id for o in draft.observations})
            identifier = stable_id("problem", draft.problem, draft.target_user, *source_ids)
            problems.append(Problem(identifier, draft, source_ids, draft.observations))
    # Identical draft duplicates must not make the partition contract impossible.
    merged = {}
    for item in problems:
        if item.id in merged:
            merged[item.id].observations.extend(o for o in item.observations if o not in merged[item.id].observations)
        else:
            merged[item.id] = item
    return list(merged.values())


def partition(items: list, instruction: str, topic: str, ask) -> list[list[str]]:
    if len(items) < 2:
        return [[item.id] for item in items]
    result = ask("project_ideator", prompts.prompt(instruction, topic=topic, items=items), MergeResult)
    ids = [identifier for group in result.groups for identifier in group.ids]
    if any(not group.ids for group in result.groups) or sorted(ids) != sorted(item.id for item in items):
        raise ValueError("Deduplication must partition every ID exactly once")
    return [group.ids for group in result.groups]


def deduplicate_problems(problems: list[Problem], config: ProjectConfig, ask) -> list[Problem]:
    lookup = {p.id: p for p in problems}
    result = []
    for group in partition(problems, prompts.PROBLEM_DEDUP_PROMPT, config.topic, ask):
        members = [lookup[key] for key in group]
        observations = []
        for item in members:
            observations.extend(o for o in item.observations if o not in observations)
        representative = members[0]
        result.append(replace(representative, observations=observations,
                              description=replace(representative.description, observations=observations),
                              source_signal_ids=sorted({s for item in members for s in item.source_signal_ids})))
    return result[:config.max_problems]


def generate_project_ideas(problems: list[Problem], config: ProjectConfig, profile: str, knowledge: str,
                           ask) -> list[ProjectIdea]:
    if not problems:
        return []
    ideas = []
    for batch in batches(problems, config.batch_size):
        remaining = config.max_ideas - len(ideas)
        if remaining <= 0:
            break
        result = ask("project_ideator", prompts.prompt(prompts.PROJECT_IDEATION_PROMPT,
                     topic=config.topic, profile=profile, knowledge=knowledge, problems=batch,
                     max_ideas=remaining, max_competitor_pages=config.max_competitor_pages), IdeationResult)
        lookup = {p.id: p for p in batch}
        counts = {p.id: 0 for p in batch}
        if len(result.ideas) > remaining:
            raise ValueError("Ideation exceeded max_ideas")
        for draft in result.ideas:
            if not draft.name.strip() or not draft.problem_ids or set(draft.problem_ids) - set(lookup):
                raise ValueError("Idea needs a name and known problem IDs")
            if len(draft.competitor_urls) > config.max_competitor_pages:
                raise ValueError("Idea exceeded competitor page budget")
            for key in set(draft.problem_ids):
                counts[key] += 1
                if counts[key] > 3:
                    raise ValueError("More than three ideas for one problem")
            sources = sorted({s for key in draft.problem_ids for s in lookup[key].source_signal_ids})
            ideas.append(ProjectIdea(stable_id("idea", draft.name, draft.proposed_solution, *draft.problem_ids),
                                     draft, sources))
    ideas = list({i.id: i for i in ideas}.values())
    lookup = {i.id: i for i in ideas}
    unique = []
    for group in partition(ideas, prompts.IDEA_DEDUP_PROMPT, config.topic, ask):
        members = [lookup[key] for key in group]
        first = members[0]
        description = replace(first.description,
                              problem_ids=sorted({p for item in members for p in item.description.problem_ids}),
                              competitor_urls=list(dict.fromkeys(
                                  u for item in members for u in item.description.competitor_urls))
                              [:config.max_competitor_pages])
        unique.append(replace(first, description=description,
                              source_signal_ids=sorted({s for item in members for s in item.source_signal_ids})))
    return unique
