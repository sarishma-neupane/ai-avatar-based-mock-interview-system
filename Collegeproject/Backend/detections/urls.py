from django.urls import path
from . import views

urlpatterns = [
    path('posture/', views.detect_posture_api, name='detect_posture'),
    path('faces/', views.detect_faces_api, name='detect_faces'),
    path('both/', views.detect_both_api, name='detect_both'),
    path('speakers/', views.detect_speakers_api, name='detect_speakers'),
    path('emotion/', views.detect_emotion_api, name='detect_emotion'),
    path('both_audio/', views.detect_audio_both_api, name='detect_audio_both'),
    path('session/<str:session_id>/', views.get_session_detections, name='get_session_detections'),
    path('tab-switch/', views.log_tab_switch, name='log_tab_switch'),  # NEW: Tab-switch / cheat detection
]


