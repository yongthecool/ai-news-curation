import os
import json
from pathlib import Path
from dotenv import load_dotenv
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .models import NewsSummary
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
        "saved_count": NewsSummary.objects.count(),
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


@csrf_exempt
@require_http_methods(["POST"])
def save_summary(request):
    """
    요약 결과 저장 API (단일 기사 또는 다중 기사 일괄 저장 지원)
    """
    try:
        if request.content_type == "application/json":
            body = json.loads(request.body)
        else:
            body = request.POST.dict()
    except Exception:
        return JsonResponse({"success": False, "error": "유효하지 않은 요청 데이터입니다."}, status=400)

    # 1. 다중 기사 일괄 저장 지원
    articles = body.get("articles")
    default_keyword = body.get("keyword", "").strip()

    if isinstance(articles, list) and len(articles) > 0:
        saved_items = []
        for a in articles:
            title = a.get("title", "").strip()
            summary_raw = a.get("summary") or a.get("summary_points") or ""
            if isinstance(summary_raw, list):
                summary = "\n".join(str(pt).strip() for pt in summary_raw if str(pt).strip())
            else:
                summary = str(summary_raw).strip()

            news_url = a.get("news_url") or a.get("link", "").strip()
            item_keyword = a.get("keyword", default_keyword).strip()
            selection_reason = a.get("selection_reason", "").strip()
            curator_take = a.get("curator_take", "").strip()

            if title and summary:
                item = NewsSummary.objects.create(
                    title=title,
                    summary=summary,
                    news_url=news_url,
                    keyword=item_keyword,
                    selection_reason=selection_reason,
                    curator_take=curator_take,
                )
                saved_items.append({"id": item.id, "title": item.title})

        return JsonResponse({
            "success": True,
            "message": f"총 {len(saved_items)}건의 요약 기사가 성공적으로 저장되었습니다.",
            "saved_count": len(saved_items),
            "total_saved": NewsSummary.objects.count()
        })

    # 2. 단일 기사 저장
    title = body.get("title", "").strip()
    summary_raw = body.get("summary") or body.get("summary_points") or ""
    if isinstance(summary_raw, list):
        summary = "\n".join(str(pt).strip() for pt in summary_raw if str(pt).strip())
    else:
        summary = str(summary_raw).strip()

    news_url = body.get("news_url") or body.get("link", "").strip()
    keyword = body.get("keyword", "").strip()
    selection_reason = body.get("selection_reason", "").strip()
    curator_take = body.get("curator_take", "").strip()

    if not title:
        return JsonResponse({"success": False, "error": "기사 제목이 누락되었습니다."}, status=400)
    if not summary:
        return JsonResponse({"success": False, "error": "요약 본문이 누락되었습니다."}, status=400)

    # 중복 저장 여부 확인 (동일 제목 및 링크)
    existing = NewsSummary.objects.filter(title=title, news_url=news_url).first()
    if existing:
        return JsonResponse({
            "success": True,
            "already_saved": True,
            "message": "이미 저장된 요약 기사입니다.",
            "data": {
                "id": existing.id,
                "title": existing.title,
                "created_at": existing.created_at.strftime("%Y-%m-%d %H:%M:%S")
            },
            "total_saved": NewsSummary.objects.count()
        })

    saved = NewsSummary.objects.create(
        title=title,
        summary=summary,
        news_url=news_url,
        keyword=keyword,
        selection_reason=selection_reason,
        curator_take=curator_take,
    )

    return JsonResponse({
        "success": True,
        "already_saved": False,
        "message": "성공적으로 저장되었습니다.",
        "data": {
            "id": saved.id,
            "title": saved.title,
            "created_at": saved.created_at.strftime("%Y-%m-%d %H:%M:%S")
        },
        "total_saved": NewsSummary.objects.count()
    })


@require_http_methods(["GET"])
def history(request):
    """
    나의 요약 히스토리 페이지
    """
    summaries = NewsSummary.objects.all().order_by("-created_at")
    total_count = summaries.count()

    return render(request, "news/history.html", {
        "summaries": summaries,
        "total_count": total_count,
    })


@csrf_exempt
@require_http_methods(["POST", "DELETE"])
def delete_summary(request, pk):
    """
    저장된 요약 항목 삭제 API
    """
    summary_item = get_object_or_404(NewsSummary, pk=pk)
    title = summary_item.title
    summary_item.delete()

    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or request.content_type == "application/json"
    if is_ajax:
        return JsonResponse({
            "success": True,
            "message": f"'{title}' 요약 항목이 삭제되었습니다.",
            "total_saved": NewsSummary.objects.count()
        })
    return redirect("news:history")

