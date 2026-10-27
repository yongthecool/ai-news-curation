import requests
from bs4 import BeautifulSoup
from typing import Optional

class ContentExtractor:
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    @classmethod
    def extract_article_body(cls, url: str, fallback_desc: str = "") -> str:
        """
        뉴스 기사 URL에서 본문 텍스트를 추출합니다.
        실패하거나 본문이 지나치게 짧을 경우 fallback_desc(기사 요약)를 반환합니다.
        """
        if not url:
            return fallback_desc

        try:
            resp = requests.get(url, headers=cls.DEFAULT_HEADERS, timeout=5)
            if resp.status_code != 200:
                return fallback_desc

            soup = BeautifulSoup(resp.content, "html.parser")

            # 불필요한 태그 제거
            for tag in soup(["script", "style", "header", "footer", "nav", "aside", "form"]):
                tag.decompose()

            # 네이버 뉴스 특화 본문 선택자
            naver_body = soup.select_one("#dic_area, #newsct_article, #articeBody")
            if naver_body:
                text = naver_body.get_text(separator=" ", strip=True)
                if len(text) > 100:
                    return text[:3000]

            # 일반 기사 본문 추론 선택자
            article_tag = soup.find("article")
            if article_tag:
                text = article_tag.get_text(separator=" ", strip=True)
                if len(text) > 100:
                    return text[:3000]

            # <p> 태그 모음 추론
            paragraphs = soup.find_all("p")
            p_text = " ".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])
            if len(p_text) > 100:
                return p_text[:3000]

        except Exception:
            pass

        return fallback_desc
