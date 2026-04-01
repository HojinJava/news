"""편향 분석 에이전트 — 각 뉴스의 편향도 분석 및 객관도 점수 산출."""

from __future__ import annotations

from collections import defaultdict

from models.schema import VerifiedArticle, AnalyzedArticle


# 감정적/편향적 단어 목록 (서방 편향 + 중동 편향 양쪽 포함)
EMOTIONAL_WORDS = [
    # 선정적/감정적 표현
    "shocking", "horrifying", "terrifying", "outrageous", "devastating",
    "barbaric", "savage", "brutal", "ruthless", "heinous",
    "slaughter", "massacre", "genocide", "atrocity", "carnage",
    # 서방 편향 표현
    "terrorist", "regime", "radical", "extremist", "rogue",
    "tyrant", "dictator", "aggressor", "provocateur", "thug",
    "evil", "axis of evil", "freedom fighters", "liberation",
    # 중동/반서방 편향 표현
    "crusader", "imperialist", "colonialist", "zionist", "occupier",
    "apartheid", "puppet", "stooge", "hegemon", "warmonger",
    # 감정 증폭 표현
    "unprecedented", "catastrophic", "existential", "annihilate",
    "obliterate", "destroy", "crush", "decimate",
    "heroic", "glorious", "triumphant", "righteous",
    # 일방적 프레이밍
    "unprovoked", "so-called", "alleged", "claimed",
    "propaganda", "disinformation", "brainwashed",
]


def _build_source_lookup(config: dict) -> dict[str, dict]:
    """config.yaml의 sources에서 매체명 → {bias, reliability} 매핑 생성."""
    lookup: dict[str, dict] = {}
    sources = config.get("sources", {})
    for tier in sources.values():
        if not isinstance(tier, list):
            continue
        for src in tier:
            name = src.get("name", "")
            lookup[name] = {
                "bias": src.get("bias", "center"),
                "reliability": src.get("reliability", 50),
            }
    return lookup


def _count_emotional_words(text: str) -> int:
    """텍스트에서 감정적/편향적 단어 출현 횟수를 센다."""
    lower = text.lower()
    count = 0
    for word in EMOTIONAL_WORDS:
        count += lower.count(word.lower())
    return count


def _compute_content_bias_score(article: VerifiedArticle) -> int:
    """기사 내용의 편향 점수 산출. 100 = 완전 객관."""
    text = f"{article.title} {article.summary}"
    count = _count_emotional_words(text)
    score = 100 - (count * 10)
    return max(0, min(100, score))


def _compute_objectivity(
    source_reliability: int,
    corroboration_count: int,
    content_bias_score: int,
) -> int:
    """최종 객관도 점수 산출.

    - 매체 기본 신뢰도: 40%
    - 교차 검증 수: 30%
    - 기사 내용 편향 분석: 30%
    """
    corroboration_score = min(corroboration_count * 20, 100)
    score = (
        source_reliability * 0.4
        + corroboration_score * 0.3
        + content_bias_score * 0.3
    )
    return round(score)


def _generate_bias_note(
    source_bias: str,
    content_bias_score: int,
    objectivity_score: int,
) -> str:
    """편향 분석 설명 생성 (한국어)."""
    bias_labels = {
        "left": "좌파 성향",
        "center-left": "중도좌파 성향",
        "center": "중도 성향",
        "center-right": "중도우파 성향",
        "right": "우파 성향",
    }
    bias_label = bias_labels.get(source_bias, "알 수 없는 성향")

    if content_bias_score >= 80:
        tone = "사실 중심의 객관적 보도"
    elif content_bias_score >= 50:
        tone = "일부 감정적 표현이 포함된 보도"
    else:
        tone = "감정적/편향적 표현이 다수 포함된 보도"

    return f"매체 성향: {bias_label}. {tone}. 객관도 점수: {objectivity_score}/100."


def _generate_framing_comparison(
    cluster_articles: list[tuple[VerifiedArticle, str, int]],
) -> str:
    """같은 클러스터 내 기사 간 프레이밍 비교 (한국어).

    cluster_articles: [(article, source_bias, content_bias_score), ...]
    """
    if len(cluster_articles) <= 1:
        return "동일 사건에 대한 비교 대상 기사가 부족합니다."

    parts: list[str] = []
    for article, bias, score in cluster_articles:
        bias_labels = {
            "left": "좌파", "center-left": "중도좌파", "center": "중도",
            "center-right": "중도우파", "right": "우파",
        }
        label = bias_labels.get(bias, "기타")
        parts.append(f"{article.source}({label}, 내용객관도:{score})")

    summary = ", ".join(parts)
    return f"동일 사건 보도 매체 비교: {summary}."


def analyze_bias(
    articles: list[VerifiedArticle],
    config: dict,
) -> list[AnalyzedArticle]:
    """검증된 기사 목록을 받아 편향 분석을 수행한다.

    Args:
        articles: Verifier가 출력한 VerifiedArticle 목록
        config: config.yaml 파싱 결과 dict

    Returns:
        편향 분석이 완료된 AnalyzedArticle 목록
    """
    source_lookup = _build_source_lookup(config)

    # 1단계: 기사별 개별 분석
    intermediate: list[tuple[VerifiedArticle, str, int, int, int]] = []
    for article in articles:
        src_info = source_lookup.get(article.source, {"bias": "center", "reliability": 50})
        source_bias = src_info["bias"]
        source_reliability = src_info["reliability"]

        content_bias_score = _compute_content_bias_score(article)
        objectivity_score = _compute_objectivity(
            source_reliability, article.corroboration_count, content_bias_score
        )
        intermediate.append((
            article, source_bias, source_reliability,
            content_bias_score, objectivity_score,
        ))

    # 2단계: 클러스터별 프레이밍 비교 준비
    clusters: dict[str, list[int]] = defaultdict(list)
    for idx, (article, *_) in enumerate(intermediate):
        if article.event_cluster_id:
            clusters[article.event_cluster_id].append(idx)

    # 클러스터별 비교 문자열 생성
    framing_map: dict[int, str] = {}
    for cluster_id, indices in clusters.items():
        cluster_data = [
            (intermediate[i][0], intermediate[i][1], intermediate[i][3])
            for i in indices
        ]
        comparison = _generate_framing_comparison(cluster_data)
        for i in indices:
            framing_map[i] = comparison

    # 3단계: AnalyzedArticle 생성
    results: list[AnalyzedArticle] = []
    for idx, (article, source_bias, source_reliability, content_bias_score, objectivity_score) in enumerate(intermediate):
        bias_note = _generate_bias_note(source_bias, content_bias_score, objectivity_score)
        framing = framing_map.get(idx, "동일 사건에 대한 비교 대상 기사가 부족합니다.")

        analyzed = AnalyzedArticle.from_verified(
            article,
            source_bias=source_bias,
            source_reliability=source_reliability,
            content_bias_score=content_bias_score,
            objectivity_score=objectivity_score,
            bias_analysis_note=bias_note,
            framing_comparison=framing,
        )
        results.append(analyzed)

    return results
