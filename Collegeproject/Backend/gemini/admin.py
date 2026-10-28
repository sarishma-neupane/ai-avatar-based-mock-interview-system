from django.contrib import admin
from .models import (
    GeminiConversation,
    GeminiMessage,
    GeminiQuestionGeneration,
    GeminiAPIUsage
)


@admin.register(GeminiConversation)
class GeminiConversationAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'user', 'title', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['session_id', 'title', 'user__username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(GeminiMessage)
class GeminiMessageAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'role', 'content_preview', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['content', 'conversation__session_id']
    readonly_fields = ['created_at']
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content'


@admin.register(GeminiQuestionGeneration)
class GeminiQuestionGenerationAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'user', 'job_role', 'years_of_experience', 'question_count', 'created_at']
    list_filter = ['created_at', 'job_role']
    search_fields = ['session_id', 'job_role', 'user__username']
    readonly_fields = ['created_at']
    
    def question_count(self, obj):
        return len(obj.questions) if obj.questions else 0
    question_count.short_description = 'Questions'


@admin.register(GeminiAPIUsage)
class GeminiAPIUsageAdmin(admin.ModelAdmin):
    list_display = ['endpoint', 'user', 'session_id', 'tokens_used', 'success', 'response_time_ms', 'created_at']
    list_filter = ['endpoint', 'success', 'created_at']
    search_fields = ['session_id', 'endpoint', 'user__username']
    readonly_fields = ['created_at']
