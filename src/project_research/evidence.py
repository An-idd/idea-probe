"""Fetched content, exact quotations and conservative independent-demand counting."""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import httpx

from api_retry import retry_http
from research_io import run_parallel

from . import prompts
from .config import ProjectConfig
from .schemas import (Document, Evidence, EvidencePack, EvidenceSelection, EvidenceSelections, Problem,
                      ProjectIdea, Signal, stable_id)
from .signals import canonical_url, document


def public_url(url: str) -> str:
    url = canonical_url(url)
    parsed = urlsplit(url)
    if parsed.port not in (None, 80, 443):
        raise ValueError("Competitor URLs must use standard HTTP(S) ports")
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Competitor URL does not resolve to public addresses")
    return url


def fetch_competitor(url: str, idea: ProjectIdea, config: ProjectConfig) -> Document:
    def read_page(target: str) -> httpx.Response:
        with httpx.stream("GET", target, timeout=20, follow_redirects=False,
                          headers={"User-Agent": "AutoResearch Project Research"}) as stream:
            chunks, size = [], 0
            for chunk in stream.iter_bytes():
                size += len(chunk)
                if size > 1_000_000:
                    raise ValueError("Competitor page exceeds the 1 MB content limit")
                chunks.append(chunk)
            # iter_bytes already decodes Content-Encoding; do not decode the buffered body again.
            headers = {k: v for k, v in stream.headers.items() if k not in ("content-encoding", "content-length")}
            return httpx.Response(stream.status_code, headers=headers, content=b"".join(chunks),
                                  request=stream.request)
    # Every redirect is revalidated, including redirects to a different host.
    for _ in range(4):
        url = public_url(url)
        response = retry_http(lambda: read_page(url), operation_name="Competitor page")
        if response.is_redirect:
            url = urljoin(url, response.headers["location"])
            continue
        response.raise_for_status()
        if "html" not in response.headers.get("content-type", "text/html"):
            raise ValueError("Competitor page must be HTML")
        soup = BeautifulSoup(response.text[:1_000_000], "html.parser")
        for node in soup(["script", "style", "nav", "header", "footer"]):
            node.decompose()
        content = soup.find("article") or soup.find("main") or soup
        text = content.get_text(" ", strip=True)[:config.max_document_chars]
        if not text:
            raise ValueError("Competitor page has no readable content")
        signal = Signal(idea.source_signal_ids[0], "competitor_page", "web", "", url, text)
        return document(signal, text)
    raise ValueError("Too many competitor page redirects")


def independent_groups(items: list[Evidence]) -> list[list[str]]:
    """Connected components: same thread, known author, repository or repeated quote count once."""
    groups: list[tuple[set[str], list[str]]] = []
    for item in items:
        if item.evidence_type != "problem":
            continue
        keys = {"thread:" + item.thread, "quote:" + " ".join(item.quote.lower().split())}
        if item.author and item.author.lower() not in ("[deleted]", "[removed]", "unknown"):
            platform = "reddit" if item.source.startswith("reddit") else item.source
            keys.add(f"author:{platform}:{item.author.lower()}")
        if item.repository:
            keys.add("repo:" + item.repository.lower())
        ids = [item.id]
        unrelated = []
        # ponytail: quadratic union is bounded by the small Evidence Pack; use union-find if packs grow.
        for existing, members in groups:
            if existing & keys:
                keys |= existing
                ids.extend(members)
            else:
                unrelated.append((existing, members))
        # A bridge can connect an earlier group after merging a later group.
        while any(existing & keys for existing, _ in unrelated):
            pending = []
            for existing, members in unrelated:
                if existing & keys:
                    keys |= existing
                    ids.extend(members)
                else:
                    pending.append((existing, members))
            unrelated = pending
        groups = unrelated + [(keys, ids)]
    return [sorted(set(ids)) for _, ids in groups]


def make_evidence(selection: EvidenceSelection, documents: dict[str, Document]) -> Evidence:
    doc = documents.get(selection.document_id)
    if not doc or not selection.quote.strip() or selection.quote not in doc.text or not selection.finding.strip():
        raise ValueError("Evidence needs an exact quote and finding from a known document")
    if selection.evidence_type == "problem" and (doc.source_type != "community"
                                                or doc.source in ("competitor_page", "github_trending")):
        raise ValueError("Repository/competitor descriptions do not establish user demand")
    return Evidence(stable_id("ev", doc.id, selection.quote, selection.evidence_type), doc.source, doc.url,
                    selection.finding, selection.evidence_type, selection.quote, doc.id, doc.signal_id,
                    doc.thread, doc.author, doc.repository)


def collect_evidence(ideas: list[ProjectIdea], problems: list[Problem], signals: list[Signal],
                     config: ProjectConfig, ask, provider=None) -> list[EvidencePack]:
    fetch = provider or fetch_competitor
    def collect(idea: ProjectIdea) -> EvidencePack:
        # Include the full collected corpus for corroboration beyond the idea's originating post.
        docs = {d.id: d for s in signals for d in s.documents}
        errors = [str(s.raw_metadata["content_error"]) for s in signals if "content_error" in s.raw_metadata]
        linked = [u for s in signals if s.id in idea.source_signal_ids for u in s.related_urls]
        urls = list(dict.fromkeys(idea.description.competitor_urls + linked))[:config.max_competitor_pages]
        competitor_ids = set()
        for url in urls:
            try:
                page = fetch(url, idea, config)
                if not page.text or not page.url:
                    raise ValueError("Empty competitor document")
                docs[page.id] = page
                competitor_ids.add(page.id)
            except Exception as exc:
                message = f"Competitor fetch failed: {url}: {exc}"
                errors.append(message)
                logging.warning("[Evidence] %s", message)
        selections = []
        terms = set(re.findall(r"[a-z][a-z0-9_]{2,}|[\u3400-\u9fff]",
                               (idea.description.one_liner + " " + idea.description.proposed_solution).lower()))
        def priority(doc):
            return (doc.id in competitor_ids, doc.signal_id in idea.source_signal_ids,
                    sum(term in doc.text.lower() for term in terms))
        # ponytail: bounded lexical retrieval; replace with semantic retrieval if corroboration recall is inadequate.
        candidates = sorted(docs.values(), key=priority, reverse=True)[:config.max_evidence_documents]
        if len(candidates) < len(docs):
            errors.append(f"Evidence retrieval evaluated {len(candidates)}/{len(docs)} documents; coverage is limited")
        for start in range(0, len(candidates), config.batch_size):
            batch = candidates[start:start + config.batch_size]
            result = ask("project_validator", prompts.prompt(prompts.EVIDENCE_PROMPT,
                         idea=idea, documents=batch, topic=config.topic), EvidenceSelections)
            allowed = {d.id for d in batch}
            if any(item.document_id not in allowed for item in result.items):
                raise ValueError("Evidence selection cites a document outside the supplied batch")
            selections.extend(result.items)
        items = list({e.id: e for e in (make_evidence(s, docs) for s in selections)}.values())
        for item in items:
            if item.evidence_type == "problem" and item.document_id in competitor_ids:
                raise ValueError("Fetched competitor pages cannot count as user demand")
        groups = independent_groups(items)
        # Preserve source provenance even when no observation qualifies as demand.
        for problem in problems:
            if problem.id in idea.description.problem_ids:
                for obs in problem.observations:
                    entry = make_evidence(
                        EvidenceSelection(obs.document_id, obs.quote, obs.finding, "provenance"), docs)
                    if entry.id not in {e.id for e in items}:
                        items.append(entry)
        retained = {d.id for d in candidates} | {e.document_id for e in items}
        return EvidencePack(idea.id, items, [d for d in docs.values() if d.id in retained], len(groups), groups, errors)
    return run_parallel(collect, ideas, config.codex.max_concurrency)
