from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
import uuid
import json

from .models import PostureDetection, FaceDetection, DetectionSession, SpeakerDetection, EmotionDetection, TabSwitchEvent
from .ml_utils import detect_posture, detect_faces, base64_to_image, detect_multiple_speakers, base64_to_audio, detect_emotion


@api_view(['POST'])
@permission_classes([AllowAny])  # Change to IsAuthenticated if you want authentication
def detect_posture_api(request):
    """
    API endpoint to detect posture from image
    
    Expected payload:
    {
        "image": "base64_encoded_image_string",
        "session_id": "optional_session_id"
    }
    """
    try:
        image_base64 = request.data.get('image')
        if not image_base64:
            return Response(
                {'error': 'Image data is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Convert base64 to image array
        image_array = base64_to_image(image_base64)
        
        # Detect posture
        result = detect_posture(image_array)
        
        if result is None:
            return Response(
                {'error': 'No landmarks detected in image'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get session_id or create new one
        session_id = request.data.get('session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Get user if authenticated (handle case where request.user might be None)
        try:
            user = request.user if request.user and request.user.is_authenticated else None
        except (AttributeError, TypeError):
            user = None
        
        # Save to database
        posture_detection = PostureDetection.objects.create(
            user=user,
            posture_label=result['posture_label'],
            confidence=result.get('confidence'),
            session_id=session_id
        )
        
        return Response({
            'success': True,
            'posture_label': result['posture_label'],
            'confidence': result.get('confidence'),
            'session_id': session_id,
            'detection_id': posture_detection.id,
            'timestamp': posture_detection.timestamp
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])  # Change to IsAuthenticated if you want authentication
def detect_faces_api(request):
    """
    API endpoint to detect faces from image
    
    Expected payload:
    {
        "image": "base64_encoded_image_string",
        "session_id": "optional_session_id"
    }
    """
    try:
        image_base64 = request.data.get('image')
        if not image_base64:
            return Response(
                {'error': 'Image data is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Convert base64 to image array
        image_array = base64_to_image(image_base64)
        
        # Detect faces
        result = detect_faces(image_array)
        
        # Get session_id or create new one
        session_id = request.data.get('session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Get user if authenticated (handle case where request.user might be None)
        try:
            user = request.user if request.user and request.user.is_authenticated else None
        except (AttributeError, TypeError):
            user = None
        
        # Save to database
        face_detection = FaceDetection.objects.create(
            user=user,
            face_count=result['face_count'],
            detections=result['detections'],
            session_id=session_id
        )
        
        return Response({
            'success': True,
            'face_count': result['face_count'],
            'detections': result['detections'],
            'session_id': session_id,
            'detection_id': face_detection.id,
            'timestamp': face_detection.timestamp
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Throttling counters
_posture_face_counter = 0
_speaker_counter = 0
_emotion_counter = 0

@api_view(['POST'])
@permission_classes([AllowAny])
def detect_both_api(request):
    """
    API endpoint to detect both posture and faces from image in one call
    Saves to DB only every 10th request to prevent locking.
    """
    global _posture_face_counter
    try:
        image_base64 = request.data.get('image')
        if not image_base64:
            return Response({'error': 'Image data is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        image_array = base64_to_image(image_base64)
        posture_result = detect_posture(image_array)
        face_result = detect_faces(image_array)
        
        session_id = request.data.get('session_id') or str(uuid.uuid4())
        
        # Throttled save
        _posture_face_counter += 1
        if _posture_face_counter >= 10:
            _posture_face_counter = 0
            try:
                user = request.user if request.user and request.user.is_authenticated else None
                if posture_result:
                    PostureDetection.objects.create(
                        user=user,
                        posture_label=posture_result['posture_label'],
                        confidence=posture_result.get('confidence'),
                        session_id=session_id
                    )
                FaceDetection.objects.create(
                    user=user,
                    face_count=face_result['face_count'],
                    detections=face_result['detections'],
                    session_id=session_id
                )
            except Exception as db_err:
                print(f"Database write skipped due to lock: {db_err}")

        return Response({
            'success': True,
            'posture': {
                'posture_label': posture_result['posture_label'] if posture_result else None,
                'confidence': posture_result.get('confidence') if posture_result else None,
            },
            'faces': {
                'face_count': face_result['face_count'],
                'detections': face_result['detections'],
            },
            'session_id': session_id
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def detect_speakers_api(request):
    """API endpoint to detect multiple speakers. Throttled save."""
    global _speaker_counter
    try:
        audio_base64 = request.data.get('audio')
        if not audio_base64:
            return Response({'error': 'Audio data is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        session_id = request.data.get('session_id') or str(uuid.uuid4())
        
        # Get reference embedding from session
        session = None
        reference_embedding = None
        if session_id:
            try:
                session = DetectionSession.objects.get(session_id=session_id)
                reference_embedding = session.reference_embedding
            except DetectionSession.DoesNotExist:
                # Create session if it doesn't exist
                session = DetectionSession.objects.create(session_id=session_id)
        
        sampling_rate = request.data.get('sampling_rate', 16000)
        audio_array, actual_sr = base64_to_audio(audio_base64, sampling_rate)
        result = detect_multiple_speakers(audio_array, actual_sr, reference_embedding=reference_embedding)
        
        # Enrollment: Save embedding if we don't have one yet and user is speaking
        if session and session.reference_embedding is None and result['has_speech'] and 'current_embedding' in result:
            session.reference_embedding = result['current_embedding']
            session.save()
            print(f"Enrolled speaker for session {session_id}")
        
        _speaker_counter += 1
        if _speaker_counter >= 10:
            _speaker_counter = 0
            try:
                user = request.user if request.user and request.user.is_authenticated else None
                SpeakerDetection.objects.create(
                    user=user,
                    has_speech=result['has_speech'],
                    is_multiple_speakers=result['is_multiple_speakers'],
                    is_interviewee=result['is_interviewee'],
                    harmonic_complexity=result['harmonic_complexity'],
                    confidence=result.get('confidence'),
                    session_id=session_id
                )
            except Exception as db_err:
                print(f"Database write skipped due to lock: {db_err}")

        return Response({
            'success': True,
            'has_speech': result['has_speech'],
            'is_multiple_speakers': result['is_multiple_speakers'],
            'is_interviewee': result['is_interviewee'],
            'confidence': result.get('confidence'),
            'session_id': session_id
        }, status=status.HTTP_200_OK)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"SPEAKER DETECTION ERROR: {e}")
        # Return a safe fallback so frontend doesn't break
        return Response({
            'success': True, # Pretend success
            'has_speech': False,
            'is_multiple_speakers': False,
            'is_interviewee': True,
            'confidence': 0.0,
            'error': str(e)
        }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
def detect_emotion_api(request):
    """API endpoint to detect emotion. Throttled save."""
    global _emotion_counter
    try:
        audio_base64 = request.data.get('audio')
        if not audio_base64:
            return Response({'error': 'Audio data is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        sampling_rate = request.data.get('sampling_rate', 16000)
        audio_array, actual_sr = base64_to_audio(audio_base64, sampling_rate)
        result = detect_emotion(audio_array, actual_sr)
        
        session_id = request.data.get('session_id') or str(uuid.uuid4())
        emotion_probs = result.get('emotion_probabilities', {}) or {'neutral': 1.0}
        
        _emotion_counter += 1
        if _emotion_counter >= 10:
            _emotion_counter = 0
            try:
                user = request.user if request.user and request.user.is_authenticated else None
                if result.get('dominant_emotion'):
                    EmotionDetection.objects.create(
                        user=user,
                        dominant_emotion=result['dominant_emotion'],
                        emotion_probabilities=emotion_probs,
                        confidence=result.get('confidence', 0.0),
                        session_id=session_id
                    )
            except Exception as db_err:
                print(f"Database write skipped due to lock: {db_err}")

        return Response({
            'success': True,
            'dominant_emotion': result.get('dominant_emotion', 'neutral'),
            'confidence': result.get('confidence', 0.0),
            'has_speech': result.get('has_speech', False),
            'session_id': session_id
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def detect_audio_both_api(request):
    """API endpoint to detect both multiple speakers and emotion in one call."""
    global _speaker_counter, _emotion_counter
    try:
        audio_base64 = request.data.get('audio')
        if not audio_base64:
            return Response({'error': 'Audio data is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        session_id = request.data.get('session_id') or str(uuid.uuid4())
        sampling_rate = request.data.get('sampling_rate', 16000)
        
        # 1. Decode audio ONCE
        audio_array, actual_sr = base64_to_audio(audio_base64, sampling_rate)
        
        # 2. Get reference embedding from session for speaker detection
        session = None
        reference_embedding = None
        if session_id:
            try:
                session = DetectionSession.objects.get(session_id=session_id)
                reference_embedding = session.reference_embedding
            except DetectionSession.DoesNotExist:
                session = DetectionSession.objects.create(session_id=session_id)
        
        # 3. Run both detections
        speaker_result = detect_multiple_speakers(audio_array, actual_sr, reference_embedding=reference_embedding)
        emotion_result = detect_emotion(audio_array, actual_sr)
        
        # Enrollment: Save embedding if needed
        if session and session.reference_embedding is None and speaker_result['has_speech'] and 'current_embedding' in speaker_result:
            session.reference_embedding = speaker_result['current_embedding']
            session.save()
            print(f"Enrolled speaker for session {session_id}")
            
        # 4. Throttled Save
        _speaker_counter += 1
        _emotion_counter += 1
        
        # Save every 10th to reduce DB pressure
        if _speaker_counter >= 10:
            _speaker_counter = 0
            _emotion_counter = 0 # Synced
            try:
                user = request.user if request.user and request.user.is_authenticated else None
                # Save Speaker Info
                SpeakerDetection.objects.create(
                    user=user,
                    has_speech=speaker_result['has_speech'],
                    is_multiple_speakers=speaker_result['is_multiple_speakers'],
                    is_interviewee=speaker_result['is_interviewee'],
                    harmonic_complexity=speaker_result['harmonic_complexity'],
                    confidence=speaker_result.get('confidence'),
                    session_id=session_id
                )
                # Save Emotion Info
                if emotion_result.get('dominant_emotion'):
                    EmotionDetection.objects.create(
                        user=user,
                        dominant_emotion=emotion_result['dominant_emotion'],
                        emotion_probabilities=emotion_result.get('emotion_probabilities', {}),
                        confidence=emotion_result.get('confidence', 0.0),
                        session_id=session_id
                    )
            except Exception as db_err:
                print(f"Database write skipped due to lock: {db_err}")

        return Response({
            'success': True,
            'speaker': {
                'has_speech': speaker_result['has_speech'],
                'is_multiple_speakers': speaker_result['is_multiple_speakers'],
                'is_interviewee': speaker_result['is_interviewee'],
                'confidence': speaker_result.get('confidence'),
            },
            'emotion': {
                'dominant_emotion': emotion_result.get('dominant_emotion', 'neutral'),
                'confidence': emotion_result.get('confidence', 0.0),
                'has_speech': emotion_result.get('has_speech', False),
            },
            'session_id': session_id
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': str(e),
            # provide safe fallbacks
            'speaker': {'has_speech': False, 'is_multiple_speakers': False, 'is_interviewee': True, 'confidence': 0.0},
            'emotion': {'dominant_emotion': 'neutral', 'confidence': 0.0, 'has_speech': False}
        }, status=status.HTTP_200_OK) # Always 200 to keep frontend happy

@api_view(['GET'])
@permission_classes([AllowAny])
def get_session_detections(request, session_id):
    """Get all detections for a specific session"""
    try:
        tab_switch_count = TabSwitchEvent.objects.filter(
            session_id=session_id,
            event_type__in=['tab_hidden', 'window_blur']
        ).count()
        return Response({
            'session_id': session_id,
            'posture_detections': list(PostureDetection.objects.filter(session_id=session_id).values()[:50]),
            'face_detections': list(FaceDetection.objects.filter(session_id=session_id).values()[:50]),
            'emotion_detections': list(EmotionDetection.objects.filter(session_id=session_id).values()[:50]),
            'tab_switch_count': tab_switch_count,
            'tab_switch_events': list(TabSwitchEvent.objects.filter(session_id=session_id).values()[:100]),
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def log_tab_switch(request):
    """
    Log a tab-switch / window-blur event from the frontend.

    Expected payload:
    {
        "session_id": "...",
        "event_type": "tab_hidden" | "window_blur" | "tab_restored" | "window_focus",
        "question_id": "Q1"   # optional, whichever question was active
    }
    """
    try:
        session_id  = request.data.get('session_id')
        event_type  = request.data.get('event_type', 'tab_hidden')
        question_id = request.data.get('question_id', '')

        if not session_id:
            return Response({'error': 'session_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        valid_types = {'tab_hidden', 'window_blur', 'tab_restored', 'window_focus'}
        if event_type not in valid_types:
            event_type = 'tab_hidden'

        try:
            user = request.user if request.user and request.user.is_authenticated else None
        except Exception:
            user = None

        event = TabSwitchEvent.objects.create(
            user=user,
            session_id=session_id,
            event_type=event_type,
            question_id=question_id or ''
        )

        # Count total suspicious events (hide + blur) for this session
        cheat_count = TabSwitchEvent.objects.filter(
            session_id=session_id,
            event_type__in=['tab_hidden', 'window_blur']
        ).count()

        print(f"[TAB-SWITCH] session={session_id} event={event_type} q={question_id} total_cheats={cheat_count}")

        return Response({
            'success': True,
            'event_id': event.id,
            'event_type': event_type,
            'tab_switch_count': cheat_count,
        }, status=status.HTTP_200_OK)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
