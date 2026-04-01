# 뉴스-시장 타임라인 / News-Market Impact Timeline

전쟁·분쟁 이벤트가 금융 시장에 미치는 영향을 시각화하는 타임라인 뷰어입니다.

A timeline viewer that visualizes how major news events (wars, conflicts) impact financial markets.

## 🔗 [라이브 보기 / Live Demo](https://hojinjava.github.io/news/)

---

## 주요 기능 / Features

- **이벤트 타임라인** — 권위 있는 출처(Wikipedia, IranWarLive)에서 수집한 전쟁 사건을 날짜별로 정렬
- **시장 영향 차트** — 각 이벤트 기준 ±30분 10분봉 차트 (유가·BTC·나스닥·코스닥)
- **관련 기사** — Reuters, AP, BBC 등 신뢰 언론의 관련 보도 (한국어 번역)
- **트럼프 X 게시물** — 이벤트와 연관된 트럼프 Truth Social / X 게시물
- **중요도 분류** — CRITICAL / MAJOR / MINOR 3단계

---

## 현재 카테고리 / Current Categories

| 카테고리 | 기간 |
|----------|------|
| 이란-이스라엘 전쟁 (2026) | 2026-02-27 ~ |

---

## 데이터 구조 / Data Structure

```
data/
└── iran-war/
    ├── config.json    # 카테고리 설정 (출처, 시장 티커 등)
    ├── news.json      # 이벤트 타임라인
    └── market.json    # 시장 OHLCV 데이터
```

---

## 로컬 실행 / Local Usage

```bash
# 1. 파일 불러오기 방식 (더블클릭)
# viewer.html을 열고 JSON 파일 선택

# 2. 로컬 서버 방식
python -m http.server 8000
# → http://localhost:8000/viewer.html
```

---

*데이터는 자동화 파이프라인으로 주기적으로 업데이트됩니다.*
