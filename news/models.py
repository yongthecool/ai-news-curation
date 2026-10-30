from django.db import models

class NewsSummary(models.Model):
    """
    뉴스 기사 요약 및 큐레이션 결과 저장 모델
    """
    keyword = models.CharField(max_length=200, blank=True, verbose_name="검색 키워드")
    title = models.CharField(max_length=500, verbose_name="기사 제목")
    summary = models.TextField(verbose_name="요약 본문")
    news_url = models.URLField(max_length=1000, blank=True, verbose_name="뉴스 링크")
    selection_reason = models.TextField(blank=True, verbose_name="선정 이유")
    curator_take = models.TextField(blank=True, verbose_name="시사점/한줄평")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="저장 시간")

    class Meta:
        verbose_name = "뉴스 요약 히스토리"
        verbose_name_plural = "뉴스 요약 히스토리 목록"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {self.title}"

    @property
    def summary_lines(self):
        """요약 본문을 줄바꿈 단위 리스트로 반환"""
        if not self.summary:
            return []
        return [line.strip() for line in self.summary.split("\n") if line.strip()]
