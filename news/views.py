import os
import json
from pathlib import Path
from dotenv import load_dotenv
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
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


# ==========================================
# 1. 사용자 인증 뷰 (로그인 / 회원가입 / 로그아웃)
# ==========================================

@require_http_methods(["GET", "POST"])
def login_view(request):
    """사용자 로그인 뷰"""
    if request.user.is_authenticated:
        return redirect("news:index")

    next_url = request.POST.get("next") or request.GET.get("next") or "news:index"
    error = None

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect(next_url)
        else:
            error = "아이디 또는 비밀번호가 올바르지 않습니다."
    else:
        form = AuthenticationForm()

    return render(request, "news/login.html", {
        "form": form,
        "error": error,
        "next": next_url
    })


@require_http_methods(["GET", "POST"])
def signup_view(request):
    """사용자 회원가입 뷰"""
    if request.user.is_authenticated:
        return redirect("news:index")

    error = None
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("news:index")
        else:
            errors_list = []
            for field, errs in form.errors.items():
                for e in errs:
                    errors_list.append(e)
            error = " ".join(errors_list)
    else:
        form = UserCreationForm()

    return render(request, "news/signup.html", {
        "form": form,
        "error": error
    })


@require_http_methods(["GET", "POST"])
def logout_view(request):
    """사용자 로그아웃 뷰"""
    logout(request)
    return redirect("news:login")


# ==========================================
# 2. 메인 뉴스 큐레이션 서비스 뷰
# ==========================================

@login_required(login_url="news:login")
@csrf_exempt
@require_http_methods(["GET", "POST"])
def index(request):
    api_status = check_api_keys()

    base_context = {
        "api_status": api_status,
        "default_keyword": DEFAULT_KEYWORD,
        "default_filter_prompt": DEFAULT_FILTER_PROMPT,
        "saved_count": NewsSummary.objects.filter(user=request.user).count(),
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
            # 1. 네이버 검색 API로 20개 기사 검색
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


# ==========================================
# 3. 요약 저장 및 히스토리 관리 뷰
# ==========================================

@csrf_exempt
@require_http_methods(["POST"])
def save_summary(request):
    """
    요약 결과 저장 API (로그인 사용자 전용)
    """
    if not request.user.is_authenticated:
        return JsonResponse({
            "success": False, 
            "error": "로그인이 필요한 서비스입니다.",
            "redirect": "/login/"
        }, status=401)

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
                    user=request.user,
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
            "total_saved": NewsSummary.objects.filter(user=request.user).count()
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

    # 중복 저장 여부 확인 (동일 사용자의 동일 제목 및 링크)
    existing = NewsSummary.objects.filter(user=request.user, title=title, news_url=news_url).first()
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
            "total_saved": NewsSummary.objects.filter(user=request.user).count()
        })

    saved = NewsSummary.objects.create(
        user=request.user,
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
        "total_saved": NewsSummary.objects.filter(user=request.user).count()
    })


@login_required(login_url="news:login")
@require_http_methods(["GET"])
def history(request):
    """
    나의 요약 히스토리 페이지 (로그인 사용자 전용)
    """
    summaries = NewsSummary.objects.filter(user=request.user).order_by("-created_at")
    total_count = summaries.count()

    return render(request, "news/history.html", {
        "summaries": summaries,
        "total_count": total_count,
    })


@login_required(login_url="news:login")
@csrf_exempt
@require_http_methods(["POST", "DELETE"])
def delete_summary(request, pk):
    """
    저장된 요약 항목 삭제 API (본인 소유 항목만 삭제 가능)
    """
    summary_item = get_object_or_404(NewsSummary, pk=pk, user=request.user)
    title = summary_item.title
    summary_item.delete()

    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or request.content_type == "application/json"
    if is_ajax:
        return JsonResponse({
            "success": True,
            "message": f"'{title}' 요약 항목이 삭제되었습니다.",
            "total_saved": NewsSummary.objects.filter(user=request.user).count()
        })
    return redirect("news:history")
