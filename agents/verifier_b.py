"""agents/verifier_b.py — Verifier-B: 독립적 반박 검토 (A와 독립 컨텍스트 유지).

역할: Verifier-A의 ClaimsReport를 받아 각 주장에 대해 반박을 시도한다.
     A와 동일한 결론에 도달하면 안 되며, 상충 가능성과 약점을 찾는다.
"""
from __future__ import annotations


def challenge_claims(claims_report: dict) -> dict:
    """ClaimsReport를 받아 ChallengeReport를 반환한다.

    Returns:
        {
            "challenges": {
                article_id: {
                    "challenge_note": str,
                    "confidence": int,   # 0-100
                    "flags": [str, ...]
                }
            }
        }
    """
    HIGH_BIAS_SOURCES = {"RT", "Sputnik", "IRNA", "Press TV", "ZeroHedge"}
    RELIABLE_SOURCES  = {"Reuters", "Associated Press", "AP", "BBC News", "BBC"}

    challenges: dict = {}
    cluster_map = {c["cluster_id"]: c for c in claims_report.get("clusters", [])}

    for art_id, claim in claims_report.get("claims", {}).items():
        cluster = cluster_map.get(claim["cluster_id"], {})
        sources = cluster.get("sources", [])
        flags: list[str] = []
        confidence = 50

        reliable_count = sum(1 for s in sources if s in RELIABLE_SOURCES)
        if reliable_count >= 2:
            confidence += 25
        elif len(sources) >= 3:
            confidence += 15
        elif len(sources) >= 2:
            confidence += 10

        if len(sources) == 1:
            confidence -= 20
            flags.append("단독 출처 — 독립 확인 불가")

        if claim.get("is_sensational"):
            confidence -= 15
            flags.append("선정적 표현 감지 — 과장 가능성")

        biased = [s for s in sources if s in HIGH_BIAS_SOURCES]
        if biased:
            confidence -= 10
            flags.append(f"편향 위험 매체 포함: {', '.join(biased)}")

        if reliable_count >= 1 and not biased:
            confidence += 5

        confidence = max(0, min(100, confidence))

        note_parts = flags if flags else ["반박 근거 없음 — 기본 신뢰"]
        challenges[art_id] = {
            "challenge_note": ". ".join(note_parts),
            "confidence": confidence,
            "flags": flags,
        }

    return {"challenges": challenges}
