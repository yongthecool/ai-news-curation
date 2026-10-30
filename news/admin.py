from django.contrib import admin
from .models import NewsSummary

@admin.register(NewsSummary)
class NewsSummaryAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'keyword', 'created_at')
    list_filter = ('created_at', 'keyword')
    search_fields = ('title', 'summary', 'keyword')
    readonly_fields = ('created_at',)
