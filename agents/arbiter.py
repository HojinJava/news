"""agents/arbiter.py — Arbiter: Verifier-A·B 조정 + 최종 검증 판정.

역할: Verifier-A (주장 추출)와 Verifier-B (반박)의 결과를 종합해 최종 검증 판정을 내린다.

판정 기준:
- confidence >= 70 → "verified" (신뢰도 높음)
- confidence < 40 or flags >= 2 → "flagged" (신뢰도 낮음, 주의 필요)
- 그 외 → "unverified" (확인 불가)
"""
from __future__ import annotations

from models.schema import RawArticle, VerifiedArticle


def arbitrate(
    articles: list[RawArticle],
    claims_report: dict,
    challenge_report: dict,
) -> list[VerifiedArticle]:
    """Verifier-A와 Verifier-B 결과를 종합해 최종 VerifiedArticle 목록을 반환한다.

    Args:
        articles: RawArticle 목록
        claims_report: Verifier-A 출력 {"clusters": [...], "claims": {...}}
        challenge_report: Verifier-B 출력 {"challenges": {...}}

    Returns:
        VerifiedArticle 목록 (verification_status, corroboration_count 등 포함)
    """
    art_map = {a.id: a for a in articles}
    claims = claims_report.get("claims", {})
    challenges = challenge_report.get("challenges", {})
    clusters = {c["cluster_id"]: c for c in claims_report.get("clusters", [])}

    results: list[VerifiedArticle] = []

    for art in articles:
        claim = claims.get(art.id, {})
        challenge = challenges.get(art.id, {})

        # 클러스터 정보 추출
        cluster_id = claim.get("cluster_id", "")
        cluster = clusters.get(cluster_id, {})
        sources = cluster.get("sources", [art.source])

        # Verifier-B의 신뢰도와 플래그 추출
        confidence = challenge.get("confidence", 50)
        flags = challenge.get("flags", [])

        # 최종 판정: confidence + flags 기반
        if confidence >= 70:
            status = "verified"
        elif confidence < 40 or len(flags) >= 2:
            status = "flagged"
        else:
            status = "unverified"

        # 검증 메모: A(주장) + B(반박) + 최종 신뢰도
        a_note = claim.get("note", "")
        b_note = challenge.get("challenge_note", "")
        note = f"[A] {a_note} / [B] {b_note} / 최종 신뢰도: {confidence}/100"

        # 같은 클러스터 내 다른 출처들 (corroborating sources)
        corroborating = [s for s in sources if s != art.source]

        # VerifiedArticle 생성
        verified = VerifiedArticle.from_raw(
            art,
            event_cluster_id=cluster_id,
            verification_status=status,
            corroboration_count=len(sources),
            corroborating_sources=corroborating,
            credibility_note=note,
        )
        results.append(verified)

    return results
