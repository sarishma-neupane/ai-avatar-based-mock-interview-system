from django.db import models
from django.contrib.auth.models import User


class PostureDetection(models.Model):
    """Model to store posture detection results"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    posture_label = models.CharField(max_length=50)  # appropriate, cheating, defensive
    confidence = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=100, null=True, blank=True)  # To group detections by session
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        return f"{self.posture_label} - {self.timestamp}"


class FaceDetection(models.Model):
    """Model to store face detection results"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    face_count = models.IntegerField(default=0)
    detections = models.JSONField(default=list)  # Store detection details (bbox, confidence, etc.)
    timestamp = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=100, null=True, blank=True)  # To group detections by session
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        return f"{self.face_count} faces - {self.timestamp}"


class DetectionSession(models.Model):
    """Model to track interview/detection sessions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=100, unique=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    reference_embedding = models.JSONField(null=True, blank=True)  # Store interviewee's voice print
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"Session {self.session_id} - {self.started_at}"


class SpeakerDetection(models.Model):
    """Model to store multiple speaker detection results"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    has_speech = models.BooleanField(default=False)
    is_multiple_speakers = models.BooleanField(default=False)
    harmonic_complexity = models.IntegerField(default=0)
    is_interviewee = models.BooleanField(default=True)  # Whether the speaker is the main interviewee
    confidence = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=100, null=True, blank=True)  # To group detections by session
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        status = "Multiple Speakers" if self.is_multiple_speakers else "Single Speaker"
        return f"{status} - {self.timestamp}"


class EmotionDetection(models.Model):
    """Model to store emotion detection results from speech"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    dominant_emotion = models.CharField(max_length=50)  # Fear, Sad, angry, disgust, happy, neutral, surprise
    emotion_probabilities = models.JSONField(default=dict)  # Store all emotion probabilities
    confidence = models.FloatField(null=True, blank=True)  # Confidence of dominant emotion
    timestamp = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=100, null=True, blank=True)  # To group detections by session
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        return f"{self.dominant_emotion} - {self.timestamp}"


class TabSwitchEvent(models.Model):
    """Model to log every time the candidate switches tab or loses browser focus during the interview."""
    EVENT_CHOICES = [
        ('tab_hidden',   'Tab Hidden (visibilitychange → hidden)'),
        ('window_blur',  'Window Blur (focus lost)'),
        ('tab_restored', 'Tab Restored (visibilitychange → visible)'),
        ('window_focus', 'Window Focus (focus regained)'),
    ]

    user       = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=100, db_index=True)
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES)
    question_id = models.CharField(max_length=100, null=True, blank=True)  # Which question was active
    timestamp  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['session_id', 'timestamp']),
        ]

    def __str__(self):
        return f"[{self.event_type}] session={self.session_id} @ {self.timestamp}"
