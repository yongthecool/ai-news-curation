import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict, Any
from .content_extractor import ContentExtractor

ENV_PATH = Path(__file__).resolve().parent.parent.parent / '.env'

class GeminiCuratorService:
    @classmethod
    def get_api_key(cls) -> str:
        load_dotenv(ENV_PATH, override=True)
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                ".env 파일에 GEMINI_API_KEY가 설정되지 않았습니다. "
                "Google AI Studio(aistudio.google.com)에서 발급받은 API 키를 .env 파일에 입력해주세요."
            )
        return api_key

    @classmethod
    def curate_and_summarize(
        cls,
        articles: List[Dict[str, Any]],
        keyword: str,
        filter_prompt: str
    ) -> List[Dict[str, Any]]:
        """
        1) 20개 기사 중 제목과 필터링 프롬프트를 기반으로 AI가 3개 기사를 선정
        2) 선정된 3개 기사에 대해 상세 3줄 요약 및 인사이트 생성
        """
        api_key = cls.get_api_key()

        # 기사 목록 텍스트 생성 (번호, 제목, 설명)
        articles_overview = []
        for a in articles:
            articles_overview.append(f"[{a['id']}] {a['title']}")
        articles_text = "\n".join(articles_overview)

        prompt = f"""당신은 전문 뉴스 큐레이터이자 시니어 에디터입니다.
검색 키워드 '{keyword}'에 대해 네이버 뉴스 검색으로 수집된 총 {len(articles)}개의 기사 제목 목록이 있습니다.

사용자의 [필터링 프롬프트] 기준을 엄격하게 적용하여, 가장 관련성이 높고 유익하며 기준에 부합하는 기사 딱 3개를 선정해주세요.

[필터링 프롬프트]
"{filter_prompt}"

[검색된 20개 기사 목록]
{articles_text}

[선정 및 요약 작업 지침]
1. 위 20개 기사 목록 중 사용자의 필터링 프롬프트 의도에 가장 완벽히 부합하는 3개의 기사를 엄선하십시오.
2. 반드시 JSON 형식으로만 응답해야 하며, 마크다운 코드블록(```json) 없이 순수 JSON 객체 또는 배열 형식으로 작성하십시오.

응답 JSON 구조:
{{
  "selected_articles": [
    {{
      "id": 1, // 위 목록의 기사 번호 (숫자)
      "selection_reason": "사용자의 필터링 기준에 비추어 이 기사를 선정한 명확한 이유 (1~2문장)",
      "curator_take": "큐레이터의 한 줄 평가 또는 핵심 시사점",
      "keywords": ["핵심키워드1", "핵심키워드2", "핵심키워드3"]
    }}
  ]
}}
"""

        response_text = cls._call_gemini(prompt, api_key)
        parsed_data = cls._parse_json(response_text)

        selected_items = parsed_data.get("selected_articles", [])
        if not selected_items and isinstance(parsed_data, list):
            selected_items = parsed_data

        article_map = {a["id"]: a for a in articles}
        curated_results = []

        # 선정된 기사 매핑
        for item in selected_items[:3]:
            aid = item.get("id")
            if aid in article_map:
                base_article = article_map[aid]
                curated_results.append({
                    "id": aid,
                    "title": base_article["title"],
                    "link": base_article["link"],
                    "pub_date": base_article["pub_date"],
                    "description": base_article["description"],
                    "selection_reason": item.get("selection_reason", "필터링 기준에 가장 적합한 기사로 선정되었습니다."),
                    "curator_take": item.get("curator_take", ""),
                    "keywords": item.get("keywords", [keyword]),
                })

        # 만약 AI 응답 파싱 등으로 3개가 안 채워졌을 경우 상위 기사로 보충
        if len(curated_results) < 3:
            used_ids = {c["id"] for c in curated_results}
            for a in articles:
                if a["id"] not in used_ids:
                    curated_results.append({
                        "id": a["id"],
                        "title": a["title"],
                        "link": a["link"],
                        "pub_date": a["pub_date"],
                        "description": a["description"],
                        "selection_reason": "필터링 기준 상위 추천 기사",
                        "curator_take": "중요 뉴스 브리핑",
                        "keywords": [keyword],
                    })
                if len(curated_results) == 3:
                    break

        # 선정된 3개 기사에 대해 상세 본문 추출 및 최종 3줄 요약 생성
        cls._enrich_summaries(curated_results, api_key)

        return curated_results

    @classmethod
    def _enrich_summaries(cls, curated_articles: List[Dict[str, Any]], api_key: str):
        """
        선정된 3개 기사의 본문을 추출하고, Gemini를 통해 3줄 핵심 요약을 생성합니다.
        """
        articles_to_summarize = []
        for a in curated_articles:
            body = ContentExtractor.extract_article_body(a["link"], fallback_desc=a["description"])
            articles_to_summarize.append({
                "id": a["id"],
                "title": a["title"],
                "content": body[:2000]
            })

        prompt = f"""다음은 최종 선정된 3개 뉴스 기사의 제목과 본문 내용입니다.
각 기사에 대해 바쁜 현대인이 핵심을 즉시 파악할 수 있도록 '3줄 핵심 요약'을 작성해 주세요.
각 요약 문장은 '~다.' 체로 끝나며 명확하고 사실에 기반해야 합니다.

[기사 목록]
{json.dumps(articles_to_summarize, ensure_ascii=False, indent=2)}

반드시 다음 JSON 형식으로만 응답하세요:
{{
  "summaries": [
    {{
      "id": 1,
      "summary_points": [
        "첫 번째 핵심 요약 문장",
        "두 번째 핵심 요약 문장",
        "세 번째 핵심 요약 문장"
      ]
    }}
  ]
}}
"""
        try:
            resp_text = cls._call_gemini(prompt, api_key)
            parsed = cls._parse_json(resp_text)
            summary_list = parsed.get("summaries", [])
            summary_map = {s.get("id"): s.get("summary_points", []) for s in summary_list}

            for a in curated_articles:
                points = summary_map.get(a["id"])
                if points and isinstance(points, list) and len(points) > 0:
                    a["summary_points"] = points
                else:
                    a["summary_points"] = [
                        a["description"] or "기사 원문을 참조해 주시기 바랍니다."
                    ]
        except Exception:
            for a in curated_articles:
                a["summary_points"] = [
                    a["description"] or "기사 원문을 참조해 주시기 바랍니다."
                ]

    @classmethod
    def _call_gemini(cls, prompt: str, api_key: str) -> str:
        """
        google-genai 최신 SDK를 우선 사용하고, 문제 발생 시 google-generativeai로 폴백합니다.
        """
        models_to_try = [
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite",
            "gemini-3.8-flash"
        ]

        last_error = ""
        # 1. 최신 google.genai 시도
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            for model_name in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.2,
                        )
                    )
                    if response and response.text:
                        return response.text
                except Exception as ex:
                    last_error = f"{model_name}: {str(ex)}"
                    continue
        except Exception as e:
            last_error = f"genai Client init error: {str(e)}"

        raise RuntimeError(f"Gemini AI 호출에 실패했습니다. (원인: {last_error})")



    @classmethod
    def _parse_json(cls, text: str) -> Dict[str, Any]:
        """
        마크다운 코드블록이나 불필요한 공백을 제거하고 안전하게 JSON을 파싱합니다.
        """
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # 중괄호나 대괄호 블록 추출 시도
            match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            raise ValueError(f"AI 응답을 JSON으로 변환할 수 없습니다: {text[:200]}")
