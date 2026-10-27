import os
import json
from pathlib import Path
from dotenv import load_dotenv
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .services.naver_search import NaverSearchService
from .services.gemini_curator import GeminiCuratorService

ENV_PATH = Path(__file__).resolve().parent.parent / '.env'

def check_api_keys():
    load_dotenv(ENV_PATH, override=True)
    naver_id = bool(os.getenv("NAVER_CLIENT_ID", "").strip())
    naver_secret = bool(os.getenv("NAVER_CLIENT_SECRET", "").strip())
    gemini_key = bool(os.getenv("GEMINI_API_KEY", "").strip())
    return {
        "naver_configured": naver_id and naver_secret,
        "gemini_configured": gemini_key,
        "all_configured": naver_id and naver_secret and gemini_key
    }

DEFAULT_KEYWORD = "생성형 AI 인공지능"
DEFAULT_FILTER_PROMPT = "단순 행사나 홍보성 기사는 제외하고, 실제 기술적 혁신이나 비즈니스 파급력이 큰 기사 위주로 골라줘."

@csrf_exempt
@require_http_methods(["GET", "POST"])
def index(request):
    api_status = check_api_keys()

    base_context = {
        "api_status": api_status,
        "default_keyword": DEFAULT_KEYWORD,
        "default_filter_prompt": DEFAULT_FILTER_PROMPT,
    }

    if request.method == "POST":
        is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or request.content_type == "application/json"
        
        if request.content_type == "application/json":
            try:
                body = json.loads(request.body)
                keyword = body.get("keyword", "").strip()
                filter_prompt = body.get("filter_prompt", "").strip()
                allow_demo = bool(body.get("allow_demo", False))
            except Exception:
                keyword = ""
                filter_prompt = ""
                allow_demo = False
        else:
            keyword = request.POST.get("keyword", "").strip()
            filter_prompt = request.POST.get("filter_prompt", "").strip()
            allow_demo = request.POST.get("allow_demo") == "true"

        # 유효성 검사
        if not keyword:
            error_msg = "검색 키워드를 입력해 주세요."
            if is_ajax:
                return JsonResponse({"success": False, "error": error_msg}, status=400)
            return render(request, "news/index.html", {
                **base_context,
                "error": error_msg,
                "keyword": keyword,
                "filter_prompt": filter_prompt
            })

        if not filter_prompt:
            error_msg = "AI 필터링 프롬프트를 입력해 주세요."
            if is_ajax:
                return JsonResponse({"success": False, "error": error_msg}, status=400)
            return render(request, "news/index.html", {
                **base_context,
                "error": error_msg,
                "keyword": keyword,
                "filter_prompt": filter_prompt
            })

        try:
            # 1. 네이버 검색 API로 20개 기사 검색 (네이버 키 오류 시 입력 키워드 기반 스마트 폴백)
            search_result = NaverSearchService.search_news(
                query=keyword, 
                display=20, 
                sort="sim"
            )
            raw_articles = search_result.get("articles", [])
            is_fallback = search_result.get("is_fallback", False)
            source_notice = search_result.get("source_notice", "")

            if not raw_articles:
                msg = f"'{keyword}'에 대한 검색 결과가 없습니다."
                if is_ajax:
                    return JsonResponse({"success": False, "error": msg}, status=404)
                return render(request, "news/index.html", {
                    **base_context,
                    "error": msg,
                    "keyword": keyword,
                    "filter_prompt": filter_prompt
                })

            # 2. AI가 필터링 프롬프트를 바탕으로 3개 선정 및 요약
            curated_articles = GeminiCuratorService.curate_and_summarize(
                articles=raw_articles,
                keyword=keyword,
                filter_prompt=filter_prompt
            )

            context = {
                **base_context,
                "keyword": keyword,
                "filter_prompt": filter_prompt,
                "curated_articles": curated_articles,
                "all_articles": raw_articles,
                "total_count": len(raw_articles),
                "curated_count": len(curated_articles),
                "is_fallback": is_fallback,
                "source_notice": source_notice
            }


            if is_ajax:
                return JsonResponse({"success": True, **context})
            return render(request, "news/index.html", context)

        except Exception as e:
            error_message = str(e)
            is_naver_error = "네이버 API" in error_message or "NAVER" in error_message
            if is_ajax:
                return JsonResponse({
                    "success": False, 
                    "error": error_message,
                    "is_naver_error": is_naver_error
                }, status=500)
            return render(request, "news/index.html", {
                **base_context,
                "error": error_message,
                "is_naver_error": is_naver_error,
                "keyword": keyword,
                "filter_prompt": filter_prompt
            })


    # GET 요청
    return render(request, "news/index.html", {
        **base_context,
        "keyword": DEFAULT_KEYWORD,
        "filter_prompt": DEFAULT_FILTER_PROMPT,
    })

