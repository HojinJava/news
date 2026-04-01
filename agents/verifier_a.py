"""agents/verifier_a.py — Verifier-A: 핵심 주장 추출 + 클러스터링 + 초기 검토."""
from __future__ import annotations

import re
import uuid
from models.schema import RawArticle

SENSATIONAL = re.compile(
    r"\b(BREAKING|SHOCKING|EXPLOSIVE|EXCLUSIVE|URGENT|BOMBSHELL|"
    r"breaking|shocking|explosive|exclusive|urgent|bombshell)\b"
)


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def extract_claims(articles: list[RawArticle], threshold: float = 0.35) -> dict:
    """RawArticle 목록에서 ClaimsReport를 생성한다.

    Returns:
        {
            "clusters": [{"cluster_id", "article_ids", "sources", "representative_title"}],
            "claims": {article_id: {"cluster_id", "is_sensational", "initial_status", "note"}}
        }
    """
    clusters: list[tuple[str, set[str], list[RawArticle]]] = []
    for art in articles:
        tokens = _tokenize(art.title)
        matched = False
        for cid, rep_tokens, members in clusters:
            if _jaccard(tokens, rep_tokens) > threshold:
                members.append(art)
                rep_tokens.update(tokens)
                matched = True
                break
        if not matched:
            cid = f"evt-{uuid.uuid4().hex[:8]}"
            clusters.append((cid, tokens, [art]))

    cluster_list = []
    claims = {}

    for cid, _, members in clusters:
        sources = list({m.source for m in members})
        cluster_list.append({
            "cluster_id": cid,
            "article_ids": [m.id for m in members],
            "sources": sources,
            "representative_title": members[0].title,
        })

        for art in members:
            sensational = bool(SENSATIONAL.search(art.title) or SENSATIONAL.search(art.summary))
            if len(sources) >= 2:
                status = "likely_verified"
            elif sensational:
                status = "suspicious"
            else:
                status = "unverified"

            note_parts = []
            if len(sources) >= 2:
                note_parts.append(f"{len(sources)}개 매체 보도 확인")
            else:
                note_parts.append("단독 보도")
            if sensational:
                note_parts.append("선정적 표현 감지")

            claims[art.id] = {
                "cluster_id": cid,
                "is_sensational": sensational,
                "initial_status": status,
                "note": ". ".join(note_parts),
            }

    return {"clusters": cluster_list, "claims": claims}
