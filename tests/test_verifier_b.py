from agents.verifier_b import challenge_claims

def test_challenge_claims_returns_challenge_report():
    claims_report = {
        "clusters": [
            {
                "cluster_id": "evt-001",
                "article_ids": ["art-001"],
                "sources": ["Reuters"],
                "representative_title": "US strikes Iran",
            }
        ],
        "claims": {
            "art-001": {
                "cluster_id": "evt-001",
                "is_sensational": False,
                "initial_status": "unverified",
                "note": "단독 보도",
            }
        }
    }
    report = challenge_claims(claims_report)
    assert "challenges" in report
    assert "art-001" in report["challenges"]
    assert "challenge_note" in report["challenges"]["art-001"]

def test_challenge_single_source_flags_lower_confidence():
    claims_report = {
        "clusters": [{"cluster_id": "c1", "article_ids": ["a1"], "sources": ["Unknown"], "representative_title": "BREAKING shocking news"}],
        "claims": {"a1": {"cluster_id": "c1", "is_sensational": True, "initial_status": "suspicious", "note": "선정적"}}
    }
    report = challenge_claims(claims_report)
    assert report["challenges"]["a1"]["confidence"] < 50
