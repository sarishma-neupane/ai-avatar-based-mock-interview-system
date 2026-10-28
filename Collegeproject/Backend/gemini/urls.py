from django.urls import path
from . import views

urlpatterns = [
    path('generate-questions/', views.generate_questions_api, name='generate_questions'),
    path('process-response/', views.process_user_response_api, name='process_user_response'),
    path('save-response/', views.save_user_response_api, name='save_user_response'),
    path('response/', views.save_user_response_api, name='save_user_response_alias'), # Alias for frontend compatibility
    path('responses/<str:session_id>/', views.get_user_responses, name='get_user_responses'),
    path('chat/', views.chat_api, name='chat'),
    path('conversation/<str:session_id>/', views.get_conversation_history, name='get_conversation_history'),
    path('questions/<str:session_id>/', views.get_generated_questions, name='get_generated_questions'),
    path('end-interview/', views.end_interview_api, name='end_interview'),
    path('refine-transcript/', views.refine_transcript_api, name='refine_transcript'),
    path('feedback/', views.get_feedback_report_api, name='generate_feedback_report'),
    path('generate-feedback/', views.get_feedback_report_api, name='generate_feedback_report_alias'),
    path('feedback/report/<str:session_id>/', views.get_feedback_report_api, name='get_feedback_report'),
    path('tts/', views.tts_api, name='tts_api'),
]
