#!/usr/bin/env python3
"""bundle.py — viewer.html + data JSON을 단일 HTML 파일로 번들링한다.
생성된 파일은 서버 없이 더블클릭으로 바로 열 수 있다."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def bundle(category: str | None, output: Path) -> None:
    base = Path(".")
    viewer = (base / "viewer.html").read_text(encoding="utf-8")

    # registry.json
    registry = json.loads((base / "data" / "registry.json").read_text(encoding="utf-8"))

    # 번들할 카테고리 결정
    if category:
        slugs = [category]
    else:
        slugs = [c["slug"] for c in registry.get("categories", [])]

    categories_data: dict = {}
    for slug in slugs:
        cat_base = base / "data" / slug
        config_path = cat_base / "config.json"
        news_path   = cat_base / "news.json"
        market_path = cat_base / "market.json"

        if not config_path.exists() or not news_path.exists():
            print(f"  [{slug}] config.json 또는 news.json 없음 — 건너뜀")
            continue

        categories_data[slug] = {
            "config": json.loads(config_path.read_text(encoding="utf-8")),
            "news":   json.loads(news_path.read_text(encoding="utf-8")),
            "market": json.loads(market_path.read_text(encoding="utf-8")) if market_path.exists() else {},
        }
        print(f"  [{slug}] 로드 완료")

    # 인라인 스크립트 생성
    inline_script = f"""
<script id="__bundle_data__">
(function() {{
  window.__BUNDLE__ = {{
    registry: {json.dumps(registry, ensure_ascii=False)},
    categories: {json.dumps(categories_data, ensure_ascii=False)}
  }};
}})();
</script>
"""

    # viewer.html의 fetch 로직을 번들 데이터로 교체하는 패치 스크립트
    patch_script = r"""
<script id="__bundle_patch__">
// fetch를 가로채서 번들 데이터를 반환한다
(function() {
  if (!window.__BUNDLE__) return;
  const _origFetch = window.fetch;
  window.fetch = function(url, opts) {
    const path = url.replace(/^\.\//, '').replace(/\\\\/g, '/');

    // registry.json
    if (path === 'data/registry.json') {
      return Promise.resolve(new Response(JSON.stringify(window.__BUNDLE__.registry), {status: 200}));
    }

    // data/{slug}/config.json
    const configMatch = path.match(/^data\\/([^\\/]+)\\/config\\.json$/);
    if (configMatch) {
      const slug = configMatch[1];
      const cat = window.__BUNDLE__.categories[slug];
      if (cat) return Promise.resolve(new Response(JSON.stringify(cat.config), {status: 200}));
    }

    // data/{slug}/news.json
    const newsMatch = path.match(/^data\\/([^\\/]+)\\/news\\.json$/);
    if (newsMatch) {
      const slug = newsMatch[1];
      const cat = window.__BUNDLE__.categories[slug];
      if (cat) return Promise.resolve(new Response(JSON.stringify(cat.news), {status: 200}));
    }

    // data/{slug}/market.json
    const marketMatch = path.match(/^data\\/([^\\/]+)\\/market\\.json$/);
    if (marketMatch) {
      const slug = marketMatch[1];
      const cat = window.__BUNDLE__.categories[slug];
      if (cat) return Promise.resolve(new Response(JSON.stringify(cat.market), {status: 200}));
    }

    return _origFetch(url, opts);
  };
})();
</script>
"""

    # </head> 바로 앞에 데이터+패치 삽입
    result = viewer.replace("</head>", inline_script + patch_script + "</head>", 1)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result, encoding="utf-8")
    print(f"\n번들 완료: {output}  ({output.stat().st_size // 1024} KB)")
    print("더블클릭으로 바로 열 수 있습니다.")


def main() -> None:
    parser = argparse.ArgumentParser(description="viewer.html + data → 단일 번들 HTML")
    parser.add_argument("--category", help="특정 카테고리 슬러그만 포함 (기본: 전체)")
    parser.add_argument("--output", default="viewer_bundle.html", help="출력 파일명")
    args = parser.parse_args()

    print(f"=== Bundle: {args.output} ===")
    bundle(args.category, Path(args.output))


if __name__ == "__main__":
    main()
