from django.db import models
from django.contrib.auth.models import User


class GeminiConversation(models.Model):
    """Model to store conversation sessions with Gemini"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    title = models.CharField(max_length=200, null=True, blank=True)  # Optional conversation title
    context = models.JSONField(default=dict, null=True, blank=True)  # Store conversation context/metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['-updated_at']),
            models.Index(fields=['user', '-updated_at']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        return f"Conversation {self.session_id} - {self.created_at}"


class GeminiMessage(models.Model):
    """Model to store individual messages in a conversation"""
    MESSAGE_ROLES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]
    
    conversation = models.ForeignKey(GeminiConversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=MESSAGE_ROLES)
    content = models.TextField()  # The actual message content
    metadata = models.JSONField(default=dict, null=True, blank=True)  # Store additional data (tokens, model version, etc.)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."


class GeminiQuestionGeneration(models.Model):
    """Model to store generated interview questions with ideal answers"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=100, db_index=True)
    job_role = models.CharField(max_length=200)
    years_of_experience = models.CharField(max_length=50)
    questions = models.JSONField(default=list)  # Store list of dicts: [{"question": "...", "ideal_answer": "..."}, ...]
    candidate_info = models.JSONField(default=dict, null=True, blank=True)  # Store candidate details
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        return f"Questions for {self.job_role} - {self.created_at}"
    
    def get_questions_list(self):
        """Helper method to get just the questions as a list"""
        if not self.questions:
            return []
        # Handle both old format (list of strings) and new format (list of dicts)
        if isinstance(self.questions[0], str):
            return self.questions
        return [q.get('question', '') for q in self.questions if isinstance(q, dict)]
    
    def get_question_with_answer(self, index):
        """Get a specific question with its ideal answer"""
        if not self.questions or index >= len(self.questions):
            return None
        q = self.questions[index]
        if isinstance(q, dict):
            return q
        # Old format - return question only
        return {'question': q, 'ideal_answer': None}


class GeminiUserResponse(models.Model):
    """Model to store user responses to interview questions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=100, db_index=True)
    question_id = models.CharField(max_length=100, db_index=True)  # Unique ID for the question
    question_text = models.TextField()  # The question that was asked
    user_answer = models.TextField(null=True, blank=True)  # User's spoken/typed answer (from speech-to-text)
    ideal_answer = models.TextField(null=True, blank=True)  # Original primary ideal answer
    alternative_answers = models.JSONField(default=list, null=True, blank=True)  # Alternative valid answers
    winning_ideal_answer = models.TextField(null=True, blank=True)  # The specific variant that best matched user response
    
    # Multimodal Feedback Data
    similarity_score = models.FloatField(null=True, blank=True)  # Semantic similarity to ideal answer (0.0-1.0)
    dominant_emotion = models.CharField(max_length=50, null=True, blank=True)
    emotion_confidence = models.FloatField(null=True, blank=True)
    posture_status = models.CharField(max_length=50, null=True, blank=True)
    
    # Per-Question Metrics (Counts during question duration)
    multiple_speak_count = models.IntegerField(default=0)
    multiple_faces_count = models.IntegerField(default=0)
    tab_switch_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session_id', 'question_id']),
            models.Index(fields=['session_id', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
        unique_together = [['session_id', 'question_id']]  # One response per question per session
    
    def __str__(self):
        return f"Response to {self.question_id} - {self.created_at}"


class GeminiAPIUsage(models.Model):
    """Model to track API usage for rate limiting and analytics"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    endpoint = models.CharField(max_length=100)  # e.g., 'generate_questions', 'chat'
    tokens_used = models.IntegerField(default=0)
    response_time_ms = models.IntegerField(null=True, blank=True)  # Response time in milliseconds
    success = models.BooleanField(default=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['session_id', '-created_at']),
        ]
    
    def __str__(self):
        status = "Success" if self.success else "Failed"
        return f"{self.endpoint} - {status} - {self.created_at}"
