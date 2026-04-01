"""교차 검증 에이전트 — 수집된 뉴스를 클러스터링하고 신뢰도를 판단한다."""

from __future__ import annotations

import re
import uuid
from collections import defaultdict

from models.schema import RawArticle, VerifiedArticle


# 선정적 표현 패턴
SENSATIONAL_WORDS = re.compile(
    r"\b(BREAKING|SHOCKING|EXPLOSIVE|EXCLUSIVE|URGENT|BOMBSHELL|"
    r"breaking|shocking|explosive|exclusive|urgent|bombshell)\b"
)


def _tokenize(text: str) -> set[str]:
    """소문자 영문 단어 토큰 집합을 반환한다."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    """두 토큰 집합의 Jaccard 유사도를 계산한다."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _cluster_articles(
    articles: list[RawArticle], threshold: float = 0.4
) -> dict[str, list[RawArticle]]:
    """영문 제목 Jaccard 유사도 기반으로 같은 사건 클러스터를 만든다.

    단순 그리디 방식: 각 기사를 순서대로 처리하며 기존 클러스터 중
    유사도가 threshold를 넘는 첫 번째 클러스터에 편입시킨다.
    없으면 새 클러스터를 생성한다.
    """
    clusters: list[tuple[str, set[str], list[RawArticle]]] = []

    for article in articles:
        tokens = _tokenize(article.title)
        matched = False
        for cluster_id, rep_tokens, members in clusters:
            if _jaccard(tokens, rep_tokens) > threshold:
                members.append(article)
                # 클러스터 대표 토큰을 합집합으로 확장
                rep_tokens.update(tokens)
                matched = True
                break
        if not matched:
            cid = f"evt-{uuid.uuid4().hex[:8]}"
            clusters.append((cid, tokens, [article]))

    return {cid: members for cid, _, members in clusters}


def _has_sensational_language(article: RawArticle) -> bool:
    """기사 제목이나 요약에 선정적 표현이 있는지 확인한다."""
    return bool(
        SENSATIONAL_WORDS.search(article.title)
        or SENSATIONAL_WORDS.search(article.summary)
    )


def _build_credibility_note(
    article: RawArticle,
    status: str,
    corroboration_count: int,
    sensational: bool,
) -> str:
    """한국어 신뢰도 판단 메모를 생성한다."""
    parts: list[str] = []

    if status == "verified":
        parts.append(f"{corroboration_count}개 매체에서 동일 사건을 보도하여 교차 검증됨")
    elif status == "flagged":
        parts.append("단독 보도이며 선정적 표현이 감지되어 주의 필요")
    else:
        parts.append("단독 보도로 교차 검증되지 않음")

    if sensational:
        parts.append("선정적 표현 감지됨")

    return ". ".join(parts) + "."


def verify_articles(
    articles: list[RawArticle], config: dict | None = None
) -> list[VerifiedArticle]:
    """수집된 기사 목록을 교차 검증하여 VerifiedArticle 목록을 반환한다.

    Parameters
    ----------
    articles:
        Collector가 수집한 RawArticle 리스트.
    config:
        config.yaml 딕셔너리 (현재 미사용, 향후 확장용).

    Returns
    -------
    list[VerifiedArticle]
    """
    if not articles:
        return []

    clusters = _cluster_articles(articles)
    results: list[VerifiedArticle] = []

    for cluster_id, members in clusters.items():
        distinct_sources = {m.source for m in members}
        corroboration_count = len(distinct_sources)

        for article in members:
            sensational = _has_sensational_language(article)
            corroborating = [s for s in distinct_sources if s != article.source]

            if corroboration_count >= 2:
                status = "verified"
            elif sensational:
                status = "flagged"
            else:
                status = "unverified"

            note = _build_credibility_note(
                article, status, corroboration_count, sensational
            )

            verified = VerifiedArticle.from_raw(
                article,
                event_cluster_id=cluster_id,
                verification_status=status,
                corroboration_count=corroboration_count,
                corroborating_sources=corroborating,
                credibility_note=note,
            )
            results.append(verified)

    return results
