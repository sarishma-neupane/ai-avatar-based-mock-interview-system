
from django.contrib import admin
from .models import PostureDetection, FaceDetection, DetectionSession


@admin.register(PostureDetection)
class PostureDetectionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'posture_label', 'confidence', 'session_id', 'timestamp']
    list_filter = ['posture_label', 'timestamp', 'session_id']
    search_fields = ['user__username', 'posture_label', 'session_id']
    readonly_fields = ['timestamp']


@admin.register(FaceDetection)
class FaceDetectionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'face_count', 'session_id', 'timestamp']
    list_filter = ['face_count', 'timestamp', 'session_id']
    search_fields = ['user__username', 'session_id']
    readonly_fields = ['timestamp']


@admin.register(DetectionSession)
class DetectionSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'session_id', 'user', 'started_at', 'ended_at', 'is_active']
    list_filter = ['is_active', 'started_at']
    search_fields = ['session_id', 'user__username']
    readonly_fields = ['started_at']

