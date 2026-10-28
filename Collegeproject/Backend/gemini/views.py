from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.authentication import SessionAuthentication
import uuid
import logging

from .models import (
    GeminiConversation,
    GeminiMessage,
    GeminiQuestionGeneration,
    GeminiAPIUsage,
    GeminiUserResponse
)
from .gemini_service import GeminiService
from Models.sbert_service import SBERTService
from .tts_utils import generate_speech
import asyncio
from django.http import FileResponse

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def generate_questions_api(request):
    """
    API endpoint to generate interview questions using Gemini
    Following the new AI Interview Assistant format
    
    Expected payload:
    {
        "job_role": "Software Engineer",
        "years_of_experience": "3 years",
        "candidate_name": "John Doe",  # optional
        "candidate_background": "Background info",  # optional
        "skills": ["Python", "Django", "React"],  # optional
        "question_count": 5,  # optional, defaults to 5
        "question_types": ["technical", "behavioral"],  # optional
        "session_id": "optional_session_id"
    }
    """
    try:
        job_role = request.data.get('job_role')
        years_of_experience = request.data.get('years_of_experience')
        candidate_name = request.data.get('candidate_name')
        candidate_background = request.data.get('candidate_background')
        skills = request.data.get('skills', [])
        question_count = request.data.get('question_count', 5)
        question_types = request.data.get('question_types')
        session_id = request.data.get('session_id')
        focus_areas = request.data.get('focus_areas', [])
        
        # Validate required fields
        if not job_role or not years_of_experience:
            return Response(
                {'error': 'job_role and years_of_experience are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create session_id
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Get user if authenticated (AllowAny means user might not be authenticated, which is fine)
        try:
            user = request.user if request.user.is_authenticated else None
        except Exception:
            # If there's an auth error (like invalid token), just set user to None
            user = None
        
        # Initialize Gemini service
        try:
            gemini_service = GeminiService()
        except Exception as e:
            logger.error(f"Failed to initialize Gemini service: {str(e)}")
            return Response(
                {'error': 'Gemini service initialization failed. Please check API key configuration.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Generate questions with ideal answers (new format)
        include_answers = request.data.get('include_ideal_answers', True)  # Default to True
        result = gemini_service.generate_interview_questions(
            job_role=job_role,
            years_of_experience=years_of_experience,
            candidate_name=candidate_name,
            candidate_background=candidate_background,
            skills=skills if isinstance(skills, list) else [],
            question_types=question_types,
            include_ideal_answers=include_answers,
            focus_areas=focus_areas
        )
        
        # Log API usage
        GeminiAPIUsage.objects.create(
            user=user,
            session_id=session_id,
            endpoint='generate_questions',
            tokens_used=result.get('tokens_used', 0),
            response_time_ms=result.get('response_time_ms'),
            success=result.get('success', False),
            error_message=result.get('error') if not result.get('success') else None
        )
        
        if not result.get('success'):
            return Response(
                {'error': result.get('error', 'Failed to generate questions')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # ---------------------------------------------------------
        # Save Question Generation Context (Session Metadata)
        # ---------------------------------------------------------
        # FIX: Ensure a GeminiConversation record exists for this session
        conversation, created = GeminiConversation.objects.get_or_create(
            session_id=session_id,
            defaults={
                'user': user,
                'title': f"Interview for {job_role}",
                'is_active': True
            }
        )

        question_generation = GeminiQuestionGeneration.objects.create(
            user=user,
            session_id=session_id,
            job_role=job_role,
            years_of_experience=years_of_experience,
            questions=result.get('questions', []),
            candidate_info={
                'candidate_name': candidate_name,
                'candidate_background': candidate_background,
                'skills': skills,
                'question_count': question_count
            }
        )

        # Save all questions to GeminiUserResponse upfront
        questions_data = result.get('questions', [])
        for q in questions_data:
            q_id = q.get('question_id')
            q_text = q.get('question')
            if q_text:
                ideal_ans = q.get('ideal_answer')
                if not ideal_ans:
                    logger.warning(f"Question {q_id} generated without an ideal_answer.")
                GeminiUserResponse.objects.get_or_create(
                    session_id=session_id,
                    question_id=q_id,
                    defaults={
                        'user': user,
                        'question_text': q_text,
                        'ideal_answer': ideal_ans or ('Greeting - No Evaluation' if q_id == 'GREETING' else 'Evaluation Pending'),
                        'alternative_answers': q.get('alternative_answers', [])
                    }
                )
        
        # Find the first real question to return as preloaded_next_question
        preloaded_q = None
        if len(questions_data) > 1:
            q1 = questions_data[1]
            preloaded_q = {
                'question_id': q1.get('question_id'),
                'question': q1.get('question'),
                'ideal_answer': q1.get('ideal_answer'),
                'alternative_answers': q1.get('alternative_answers', [])
            }
        
        return Response({
            'success': True,
            'session_id': session_id,
            'questions': questions_data,  # Contains the greeting
            'preloaded_next_question': preloaded_q, # Contains Question 1
            'question_count': len(questions_data), # Now just the count of all questions
            'tokens_used': result.get('tokens_used', 0),
            'response_time_ms': result.get('response_time_ms'),
            'created_at': timezone.now()
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error in generate_questions_api: {str(e)}")
        # Fallback questions so the app doesn't break
        fallback_questions = [
            {"question_id": "GREETING", "question": "Hello! Could you please introduce yourself?", "type": "greeting"},
            {"question_id": "Q1", "question": "Can you handle this specific situation properly?", "type": "technical", "ideal_answer": "Yes, I would analyze the problem."},
            {"question_id": "Q2", "question": "What are your key strengths?", "type": "technical", "ideal_answer": "I am a quick learner."},
            {"question_id": "Q3", "question": "Describe a challenging project you worked on.", "type": "technical", "ideal_answer": "I solved a complex issue."},
            {"question_id": "Q4", "question": "Where do you see yourself in 5 years?", "type": "technical", "ideal_answer": "Growing with the company."},
            {"question_id": "Q5", "question": "Do you have any questions for us?", "type": "technical", "ideal_answer": "No questions."},
             {"question_id": "CLOSING", "question": "Thank you for your time. The interview is now complete.", "type": "closing"}
        ]
        
        # Preloaded is Q1
        preloaded_q = {
            'question_id': "Q1",
            'question': "Can you handle this specific situation properly?",
            'ideal_answer': "Yes, I would analyze the problem.",
            'alternative_answers': []
        }

        return Response({
            'success': True,
            'session_id': request.data.get('session_id') or 'fallback_session',
            'questions': fallback_questions,
            'preloaded_next_question': preloaded_q,
            'question_count': len(fallback_questions),
            'tokens_used': 0,
            'note': 'Fallback content generated due to AI service error.'
        }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])  # Change to IsAuthenticated if needed
def process_user_response_api(request):
    """
    API endpoint to process user response and generate follow-up questions if needed
    Following the new AI Interview Assistant format
    
    Expected payload:
    {
        "question_id": "unique_question_id",
        "question": "Original question text",
        "user_response": "User's spoken or typed answer",
        "job_role": "Software Engineer",
        "years_of_experience": "3 years",
        "candidate_name": "John Doe",  # optional
        "session_id": "optional_session_id"
    }
    """
    try:
        question_id = request.data.get('question_id')
        question = request.data.get('question')
        user_response = request.data.get('user_response')
        job_role = request.data.get('job_role')
        years_of_experience = request.data.get('years_of_experience')
        candidate_name = request.data.get('candidate_name')
        session_id = request.data.get('session_id')
        
        # Validate required fields
        if not question_id or not question or not user_response:
            return Response(
                {'error': 'question_id, question, and user_response are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not job_role or not years_of_experience:
            return Response(
                {'error': 'job_role and years_of_experience are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create session_id
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Get user if authenticated (handle auth errors gracefully)
        try:
            user = request.user if request.user.is_authenticated else None
        except Exception:
            user = None
        
        # Initialize Gemini service
        try:
            gemini_service = GeminiService()
        except Exception as e:
            logger.error(f"Failed to initialize Gemini service: {str(e)}")
            return Response(
                {'error': 'Gemini service initialization failed. Please check API key configuration.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Process user response and generate follow-up
        result = gemini_service.process_user_response(
            question_id=question_id,
            question=question,
            user_response=user_response,
            job_role=job_role,
            years_of_experience=years_of_experience,
            candidate_name=candidate_name
        )
        
        # Log API usage
        GeminiAPIUsage.objects.create(
            user=user,
            session_id=session_id,
            endpoint='process_user_response',
            tokens_used=result.get('tokens_used', 0),
            response_time_ms=result.get('response_time_ms'),
            success=result.get('success', False),
            error_message=result.get('error') if not result.get('success') else None
        )
        
        if not result.get('success'):
            return Response(
                {'error': result.get('error', 'Failed to process user response')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response({
            'success': True,
            'session_id': session_id,
            'follow_up': result.get('follow_up', {
                'follow_up_required': False,
                'question': '',
                'ideal_answer': '',
                'alternative_answers': []
            }),
            'tokens_used': result.get('tokens_used', 0),
            'response_time_ms': result.get('response_time_ms')
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error in process_user_response_api: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])  # Change to IsAuthenticated if needed
def chat_api(request):
    """
    API endpoint for conversational chat with Gemini
    
    Expected payload:
    {
        "message": "User message",
        "session_id": "conversation_session_id",  # optional, will create new if not provided
        "conversation_history": [  # optional, for context
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"}
        ],
        "system_instruction": "Optional system instruction",
        "temperature": 0.7  # optional
    }
    """
    try:
        message = request.data.get('message')
        session_id = request.data.get('session_id')
        conversation_history = request.data.get('conversation_history', [])
        system_instruction = request.data.get('system_instruction')
        temperature = request.data.get('temperature', 0.7)
        
        # Validate required fields
        if not message:
            return Response(
                {'error': 'message is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create session_id
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Get user if authenticated (handle auth errors gracefully)
        try:
            user = request.user if request.user.is_authenticated else None
        except Exception:
            user = None
        
        # Get or create conversation
        conversation, created = GeminiConversation.objects.get_or_create(
            session_id=session_id,
            defaults={
                'user': user,
                'is_active': True
            }
        )
        
        # Initialize Gemini service
        try:
            gemini_service = GeminiService()
        except Exception as e:
            logger.error(f"Failed to initialize Gemini service: {str(e)}")
            return Response(
                {'error': 'Gemini service initialization failed. Please check API key configuration.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Build messages list for chat
        messages = []
        
        # Add conversation history from database if available
        if not conversation_history:
            db_messages = GeminiMessage.objects.filter(conversation=conversation).order_by('created_at')
            for db_msg in db_messages:
                messages.append({
                    'role': db_msg.role,
                    'content': db_msg.content
                })
        else:
            messages = conversation_history
        
        # Add current user message
        messages.append({
            'role': 'user',
            'content': message
        })
        
        # Get response from Gemini
        result = gemini_service.chat(
            messages=messages,
            system_instruction=system_instruction,
            temperature=float(temperature)
        )
        
        # Log API usage
        GeminiAPIUsage.objects.create(
            user=user,
            session_id=session_id,
            endpoint='chat',
            tokens_used=result.get('tokens_used', 0),
            response_time_ms=result.get('response_time_ms'),
            success=result.get('success', False),
            error_message=result.get('error') if not result.get('success') else None
        )
        
        if not result['success']:
            return Response(
                {'error': result.get('error', 'Failed to get response from Gemini')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Save messages to database
        user_message = GeminiMessage.objects.create(
            conversation=conversation,
            role='user',
            content=message
        )
        
        assistant_message = GeminiMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=result.get('text', ''),
            metadata={
                'tokens_used': result.get('tokens_used', 0),
                'response_time_ms': result.get('response_time_ms')
            }
        )
        
        # Update conversation timestamp
        conversation.updated_at = timezone.now()
        conversation.save()
        
        return Response({
            'success': True,
            'session_id': session_id,
            'questions': result.get('questions', []),
            'preloaded_next_question': result.get('preloaded_next_question'),
            'question_count': result.get('question_count', 0),
            'tokens_used': result.get('tokens_used', 0),
            'response_time_ms': result.get('response_time_ms'),
            'created_at': timezone.now()
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error in chat_api: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])  # Change to IsAuthenticated if needed
def get_conversation_history(request, session_id):
    """
    Get conversation history for a session
    
    URL: /api/gemini/conversation/<session_id>/
    """
    try:
        conversation = GeminiConversation.objects.filter(session_id=session_id).first()
        
        if not conversation:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        messages = GeminiMessage.objects.filter(conversation=conversation).order_by('created_at')
        
        return Response({
            'session_id': session_id,
            'created_at': conversation.created_at,
            'updated_at': conversation.updated_at,
            'messages': [
                {
                    'id': msg.id,
                    'role': msg.role,
                    'content': msg.content,
                    'created_at': msg.created_at,
                    'metadata': msg.metadata
                }
                for msg in messages
            ]
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error in get_conversation_history: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])  # Change to IsAuthenticated if needed
def save_user_response_api(request):
    """
    API endpoint to save user response to an interview question
    
    Expected payload:
    {
        "session_id": "session_id",
        "question_id": "unique_question_id",
        "question_text": "The question that was asked",
        "user_answer": "User's spoken/typed answer",
        "ideal_answer": "Ideal answer from Gemini",  # optional, can be fetched from question generation
        "alternative_answers": ["alt1", "alt2"]  # optional
    }
    """
    try:
        session_id = request.data.get('session_id')
        question_id = request.data.get('question_id')
        question_text = request.data.get('question_text')
        user_answer = request.data.get('user_answer')
        ideal_answer = request.data.get('ideal_answer')
        alternative_answers = request.data.get('alternative_answers', [])
        is_prefetch = request.data.get('is_prefetch', False)
        
        # New Multimodal Inputs
        dominant_emotion = request.data.get('dominant_emotion')
        emotion_confidence = request.data.get('emotion_confidence')
        posture_status = request.data.get('posture_status')
        
        # Validate required fields
        if not session_id or not question_id or not question_text or (not user_answer and not is_prefetch):
            return Response(
                {'error': 'session_id, question_id, question_text, and user_answer (unless prefetch) are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ---------------------------------------------------------
        # 1. FETCH EXISTING DATA (For Upfront Generation)
        # ---------------------------------------------------------
        existing_resp = GeminiUserResponse.objects.filter(session_id=session_id, question_id=question_id).first()
        if existing_resp:
            if not ideal_answer and existing_resp.ideal_answer and existing_resp.ideal_answer != 'Evaluation Pending':
                ideal_answer = existing_resp.ideal_answer
                logger.info(f"Retrieved valid ideal_answer from DB for {question_id}")
            if not alternative_answers and existing_resp.alternative_answers:
                alternative_answers = existing_resp.alternative_answers
        
        # ---------------------------------------------------------
        # 2. SCORING & EVALUATION LOGIC
        # ---------------------------------------------------------
        similarity_score = 0.0
        winning_ideal_answer = None
        is_subjective = False
        
        # Check if question is Subjective (No Evaluation) or GREETING
        if (question_id == 'GREETING') or (ideal_answer and ("subjective" in ideal_answer.lower() or "no evaluation" in ideal_answer.lower())):
            is_subjective = True
            logger.info(f"Question {question_id} identified as SUBJECTIVE/GREETING. Skipping scoring.")
        
        # Calculate Similarity if applicable
        if not is_prefetch and user_answer and not is_subjective:
            try:
                # Wrap entire SBERT logic to prevent crash
                try:
                    # ANTI-CHEAT / INVALID ANSWER DETECTION
                    # Only penalize if user explicitly admitted not knowing OR gave a trivially short answer
                    # NOTE: Do NOT use character-level SequenceMatcher for topic-related answers.
                    # Topic keywords (e.g. "list", "tuple") appear in both Q and A naturally,
                    # causing false positive high-overlap ratios even for correct answers.
                    ua_clean = user_answer.lower().strip()
                    q_clean = question_text.lower().strip()

                    ua_word_count = len(ua_clean.split())
                    q_word_count = len(q_clean.split())

                    idk_phrases = ["i don't know", "i didn't know", "no idea", "pass", "skip"]
                    has_idk = any(p in ua_clean for p in idk_phrases)

                    # Basic validation
                    if has_idk and ua_word_count < 10:
                        force_zero_score = True
                    elif ua_word_count < 2:
                        force_zero_score = True

                    comparison_texts = []
                    comparison_texts_set = set()
                    
                    # Log for debugging
                    print(f"[SBERT] Evaluating Q: {question_id} | Session: {session_id}")
                    
                    if ideal_answer and ideal_answer.strip() not in ('', 'Evaluation Pending', 'None', 'Subjective - No Evaluation'):
                        comparison_texts_set.add(ideal_answer)
                        print(f"[SBERT] Adding provided ideal_answer: {ideal_answer[:50]}...")
                    
                    if alternative_answers:
                        for alt in alternative_answers:
                            if alt and alt.strip() not in ('', 'Evaluation Pending', 'None'):
                                comparison_texts_set.add(alt)


                    # ── MUST CHECK SEMANTICALLY WITH RELEVANT ANSWERS ──────
                    # Optimization: Instead of pulling the entire DB (700+ rows),
                    # we focus locally and only pull a subset if needed.


                    # ── TIER 2: Look up from GeminiQuestionGeneration DB ──────
                    if not comparison_texts_set:
                        print(f"[SBERT] ⚠️  No ideal_answer in request. Searching DB for question_id={question_id}")
                        try:
                            q_gen_lookup = GeminiQuestionGeneration.objects.filter(session_id=session_id).first()
                            if q_gen_lookup and q_gen_lookup.questions:
                                for q_item in q_gen_lookup.questions:
                                    if q_item.get('question_id') == question_id:
                                        fetched_ideal = q_item.get('ideal_answer')
                                        fetched_alts  = q_item.get('alternative_answers', [])
                                        if fetched_ideal and fetched_ideal not in ('', 'Evaluation Pending', None):
                                            ideal_answer      = fetched_ideal
                                            comparison_texts_set.add(ideal_answer)
                                            if fetched_alts:
                                                for alt in fetched_alts:
                                                    if alt and alt not in ('', 'Evaluation Pending', 'None'):
                                                        comparison_texts_set.add(alt)
                                            print(f"[SBERT] ✅ Found ideal_answer in DB for {question_id}")
                                        break
                        except Exception as db_err:
                            print(f"[SBERT] DB lookup error: {db_err}")

                    # ── TIER 3: Generate ideal answer via Gemini (guaranteed fallback) ─
                    if not comparison_texts_set:
                        print(f"[SBERT] 🤖 Generating ideal answer via Gemini for: '{question_text[:80]}'")
                        try:
                            gem_svc = GeminiService()
                            q_ctx   = GeminiQuestionGeneration.objects.filter(session_id=session_id).first()
                            gen_result = gem_svc._generate_ideal_answer_with_alternatives(
                                question=question_text,
                                question_id=question_id,
                                job_role=q_ctx.job_role if q_ctx else "Software Engineer",
                                years_of_experience=q_ctx.years_of_experience if q_ctx else "3 years"
                            )
                            if gen_result.get('success') and gen_result.get('ideal_answer'):
                                ideal_answer       = gen_result['ideal_answer']
                                generated_alts     = gen_result.get('alternative_answers', [])
                                comparison_texts_set.add(ideal_answer)
                                for alt in generated_alts:
                                    if alt: comparison_texts_set.add(alt)
                                print(f"[SBERT] ✅ Gemini-generated ideal_answer")
                        except Exception as gen_err:
                            print(f"[SBERT] ❌ Gemini generation error: {gen_err}")

                    comparison_texts = list(comparison_texts_set)

                    print(f"[SBERT] 📊 Final comparison_texts count: {len(comparison_texts)}")

                    if not force_zero_score and comparison_texts:
                        # Initialize SBERT just in time for scoring
                        try:
                            sbert = SBERTService()
                            # Pass question_text so SBERT can apply the echo-penalty internally
                            similarity_score, winning_ideal_answer = sbert.calculate_similarity(
                                user_answer, comparison_texts, question_text=question_text
                            )
                        except Exception as sbert_init_err:
                            # Re-raise so it hits the LLM fallback below
                            raise sbert_init_err
                        # Ensure winning_ideal_answer is never the literal string "None"
                        if not winning_ideal_answer or winning_ideal_answer == "None":
                            winning_ideal_answer = ideal_answer

                        logger.info(f"SBERT Final Similarity: {similarity_score:.4f}")
                        print(f"\n{'='*50}\n[SBERT] Similarity Score: {similarity_score:.4f}\nStatus: {'Scored' if not is_subjective else 'Subjective/Skipped'}\n{'='*50}\n")
                    else:
                        similarity_score = 0.0
                        winning_ideal_answer = ideal_answer
                        print(f"\n{'='*50}\n[SBERT] Similarity Score: 0.00 (Forced/Penalty or no comparison texts)\nStatus: Penalty Applied\n{'='*50}\n")
                except Exception as sbert_err:
                    logger.error(f"SBERT Critical Failure, attempting direct Gemini Fallback: {sbert_err}")
                    try:
                        gem_svc = GeminiService()
                        res = gem_svc.calculate_semantic_similarity_llm(user_answer, comparison_texts, question_text)
                        similarity_score = res.get('score', 0.0)
                        winning_ideal_answer = res.get('best_match', ideal_answer)
                        print(f"[FALLBACK] Gemini-based similarity score: {similarity_score:.2f}")
                    except Exception as fallback_err:
                        logger.error(f"Double-Failure: Gemini fallback also failed: {fallback_err}")
                        similarity_score = 0.0
                        winning_ideal_answer = ideal_answer

            except Exception as e:
                logger.error(f"SBERT calculation outer failed: {e}") 
                similarity_score = 0.0

        # ---------------------------------------------------------
        # 2.5 MULTIMODAL COUNTS FOR CURRENT QUESTION
        # ---------------------------------------------------------
        multiple_speak_count = 0
        multiple_faces_count = 0
        tab_switch_count = 0
        
        if not is_prefetch:
            try:
                from detections.models import SpeakerDetection, FaceDetection, TabSwitchEvent
                from django.utils import timezone
                from datetime import timedelta
                
                # Find start time: either the last technical response or the greeting
                last_resp = GeminiUserResponse.objects.filter(
                    session_id=session_id
                ).exclude(question_id=question_id).filter(
                    user_answer__isnull=False
                ).order_by('-updated_at').first()
                
                if last_resp:
                    start_time = last_resp.updated_at
                else:
                    # Fallback to greeting created_at
                    greeting = GeminiUserResponse.objects.filter(session_id=session_id, question_id='GREETING').first()
                    start_time = greeting.created_at if greeting else (timezone.now() - timedelta(minutes=5))
                
                # Count alerts in this window
                multiple_speak_count = SpeakerDetection.objects.filter(
                    session_id=session_id, 
                    is_multiple_speakers=True,
                    timestamp__gte=start_time
                ).count()
                
                multiple_faces_count = FaceDetection.objects.filter(
                    session_id=session_id, 
                    face_count__gt=1,
                    timestamp__gte=start_time
                ).count()

                # Improved: Filter by question_id if available, otherwise fallback to time window
                tab_events = TabSwitchEvent.objects.filter(
                    session_id=session_id,
                    event_type__in=['tab_hidden', 'window_blur']
                )
                if question_id:
                    tab_switch_count = tab_events.filter(question_id=question_id).count()
                
                # If zero by ID, fallback to time-based count (in case ID wasn't logged correctly)
                if tab_switch_count == 0:
                    tab_switch_count = tab_events.filter(timestamp__gte=start_time).count()
                
                logger.info(f"Question {question_id} Metrics: Speakers={multiple_speak_count}, Faces={multiple_faces_count}, Tabs={tab_switch_count}")
            except Exception as e:
                logger.error(f"Error calculating per-question detection metrics: {e}")

        # ---------------------------------------------------------
        # 3. SAVE USER RESPONSE
        # ---------------------------------------------------------
        # Get user if authenticated
        try:
             user = request.user if request.user.is_authenticated else None
        except:
             user = None

        user_response = None
        created = False

        if not is_prefetch:
            if existing_resp:
                user_response = existing_resp
                user_response.user_answer = user_answer
                user_response.similarity_score = similarity_score if not is_subjective else 0
                user_response.dominant_emotion = dominant_emotion or "neutral"
                user_response.emotion_confidence = emotion_confidence or 0
                user_response.posture_status = posture_status or "unknown"
                user_response.winning_ideal_answer = winning_ideal_answer or ideal_answer
                user_response.multiple_speak_count = multiple_speak_count
                user_response.multiple_faces_count = multiple_faces_count
                user_response.tab_switch_count = tab_switch_count
                user_response.save()
                created = False
            else:
                user_response, created = GeminiUserResponse.objects.get_or_create(
                    session_id=session_id,
                    question_id=question_id,
                    defaults={
                        'user': user,
                        'question_text': question_text,
                        'user_answer': user_answer,
                        'ideal_answer': ideal_answer,
                        'winning_ideal_answer': winning_ideal_answer or ideal_answer,
                        'alternative_answers': alternative_answers if alternative_answers else [],
                        'similarity_score': similarity_score if not is_subjective else 0,
                        'dominant_emotion': dominant_emotion or "neutral",
                        'emotion_confidence': emotion_confidence or 0,
                        'posture_status': posture_status or "unknown",
                        'multiple_speak_count': multiple_speak_count,
                        'multiple_faces_count': multiple_faces_count,
                        'tab_switch_count': tab_switch_count
                    }
                )
        else:
            user_response = GeminiUserResponse.objects.filter(session_id=session_id, question_id=question_id).first()
            created = False

        # ---------------------------------------------------------
        # 3. NEXT QUESTION / FOLLOW-UP LOGIC
        # ---------------------------------------------------------
        next_question_data = None
        
        # Retrieve context
        q_gen = GeminiQuestionGeneration.objects.filter(session_id=session_id).first()
        job_role = q_gen.job_role if q_gen else "Generic Role"
        years_of_exp = q_gen.years_of_experience if q_gen else "Unknown"
        candidate_name = q_gen.candidate_info.get('candidate_name') if q_gen else None

        previous_responses = GeminiUserResponse.objects.filter(
            session_id=session_id
        ).exclude(question_id=question_id).order_by('created_at')
        
        history = []
        for resp in previous_responses:
            if resp.user_answer:
                history.append({
                    'id': resp.question_id,
                    'question': resp.question_text, 
                    'answer': resp.user_answer
                })
        
        next_question_data = None
        
        # Simplified Upfront Logic: Get next question from the pre-generated list
        q_gen = GeminiQuestionGeneration.objects.filter(session_id=session_id).first()
        all_questions = q_gen.questions if q_gen else []
        
        current_idx = -1
        for i, q in enumerate(all_questions):
            if q.get('question_id') == question_id:
                current_idx = i
                break
        if current_idx != -1 and current_idx < len(all_questions) - 1:
            next_q = all_questions[current_idx + 1]

            next_question_data = {
                'question_id': next_q.get('question_id'),
                'question': next_q.get('question'),
                'type': next_q.get('type', 'technical')
            }
            print(f"[FLOW] Moving to next pre-generated question: {next_question_data['question_id']}")
        else:
            # End Interview
            next_question_data = {
                'question_id': 'CLOSING',
                'question': f"Thank you, {candidate_name or 'Candidate'}. We have completed the session and I have enough information to evaluate your performance.",
                'type': 'closing'
            }
            print(f"[FLOW] No more questions. Ending session.")

        if next_question_data:
            next_q_obj, created = GeminiUserResponse.objects.get_or_create(
                session_id=session_id,
                question_id=next_question_data['question_id'],
                defaults={
                    'user': user,
                    'question_text': next_question_data['question'],
                    'user_answer': None,
                    'ideal_answer': 'Evaluation Pending',
                    'alternative_answers': []
                }
            )
            next_question_data = {
                'question_id': next_q_obj.question_id,
                'question': next_q_obj.question_text
            }
        else:
            # FALLBACK LOGIC: Should not happen with upfront generation
            print(f"[ERROR] No next question found in upfront list.")
            next_question_data = {
                'question_id': 'CLOSING',
                'question': "Thank you for your time. The interview is complete.",
                'type': 'closing'
            }

        # ---------------------------------------------------------
        # 4. GENERATE QUESTION-WISE FEEDBACK
        # ---------------------------------------------------------
        feedback_data = None
        
        if not is_prefetch and user_answer and not is_subjective:
            try:
                gemini_service = GeminiService()
                feedback_result = gemini_service.generate_question_feedback(
                    question=question_text,
                    user_answer=user_answer,
                    ideal_answer=ideal_answer or "No ideal answer provided",
                    similarity_score=similarity_score,
                    emotion_data={
                        'emotion': dominant_emotion or 'neutral',
                        'confidence': emotion_confidence or 0.0
                    },
                    posture_data=posture_status or 'unknown',
                    job_role=job_role,
                    years_of_experience=years_of_exp
                )
                
                if feedback_result.get('success'):
                    feedback_data = {
                        'question_id': question_id,
                        'scores': {
                            'semantic_similarity': round(similarity_score, 4),
                            'emotion_confidence': round(emotion_confidence or 0.0, 4),
                            'emotion_detected': dominant_emotion or 'neutral',
                            'posture_status': posture_status or 'unknown'
                        },
                        'positives': feedback_result.get('positives', []),
                        'negatives': feedback_result.get('negatives', [])
                    }
                    logger.info(f"Generated feedback for {question_id}: {len(feedback_result.get('positives', []))} positives, {len(feedback_result.get('negatives', []))} negatives")
            except Exception as e:
                logger.error(f"Failed to generate question feedback: {e}")
                # Continue without feedback rather than failing the entire request

        return Response({
            'success': True,
            'created': created,
            'response_id': user_response.id,
            'session_id': session_id,
            'question_id': question_id,
            'next_question': next_question_data, # Return the next question
            'feedback': feedback_data,  # NEW: Question-wise feedback with scores
            'created_at': user_response.created_at,
            'updated_at': user_response.updated_at
        }, status=status.HTTP_200_OK if created else status.HTTP_201_CREATED)
    
    except Exception as e:
        logger.error(f"Error in save_user_response_api: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])  # Change to IsAuthenticated if needed
def get_user_responses(request, session_id):
    """
    Get all user responses for a session
    
    URL: /api/gemini/responses/<session_id>/
    """
    try:
        responses = GeminiUserResponse.objects.filter(
            session_id=session_id
        ).order_by('created_at')
        
        return Response({
            'success': True,
            'session_id': session_id,
            'responses': [
                {
                    'id': resp.id,
                    'question_id': resp.question_id,
                    'question_text': resp.question_text,
                    'user_answer': resp.user_answer,
                    'ideal_answer': resp.ideal_answer,
                    'alternative_answers': resp.alternative_answers,
                    'created_at': resp.created_at,
                    'updated_at': resp.updated_at
                }
                for resp in responses
            ],
            'count': responses.count()
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error in get_user_responses: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])  # Change to IsAuthenticated if needed
def get_generated_questions(request, session_id):
    """
    Get generated questions for a session
    
    URL: /api/gemini/questions/<session_id>/
    """
    try:
        question_generation = GeminiQuestionGeneration.objects.filter(
            session_id=session_id
        ).order_by('-created_at').first()
        
        if not question_generation:
            return Response(
                {'error': 'Questions not found for this session'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response({
            'session_id': session_id,
            'job_role': question_generation.job_role,
            'years_of_experience': question_generation.years_of_experience,
            'questions': question_generation.questions,
            'candidate_info': question_generation.candidate_info,
            'created_at': question_generation.created_at,
            'generation_id': question_generation.id
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error in get_generated_questions: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def generate_feedback_report_api(request, session_id=None):
    """
    Generate comprehensive interview feedback
    """
    try:
        if not session_id:
            # Try POST body first
            session_id = request.data.get('session_id')
            
        if not session_id:
            # Try GET query parameters
            session_id = request.query_params.get('session_id')
            
        if not session_id:
            return Response({'error': 'session_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Fetch session context (Candidate Name, Job Role)

        from .models import GeminiQuestionGeneration, GeminiUserResponse
        from detections.models import TabSwitchEvent
        q_gen = GeminiQuestionGeneration.objects.filter(session_id=session_id).first()
        
        # FIX: Extract name from candidate_info JSON field
        candidate_name = "Candidate"
        if q_gen and q_gen.candidate_info:
            candidate_name = q_gen.candidate_info.get('candidate_name', 'Candidate')
            
        job_role = q_gen.job_role if q_gen else "Interviewee"
        
        # FIX: Fetch user responses for the session
        responses = GeminiUserResponse.objects.filter(session_id=session_id).order_by('created_at')
        if not responses.exists():
            return Response({'error': 'No responses found for this session'}, status=status.HTTP_404_NOT_FOUND)
        
        # Construct prompt for Gemini
        interview_data = []
        technical_scores = []
        
        for r in responses:
            if not r.user_answer: continue # Skip pending/unanswered
            
            # Identify if it's a technical question vs greeting/subjective
            is_greeting = (r.question_id == 'GREETING')
            is_subjective = (r.ideal_answer and "subjective" in r.ideal_answer.lower())
            
            # Only add to technical average if it was a scorable objective question
            if not is_greeting and not is_subjective:
                score = r.similarity_score if r.similarity_score is not None else 0.0
                technical_scores.append(score)
            else:
                score = 0.0 # Just for display if greeting/subjective
            
            # Record for transcript
            question_type_label = 'Greeting' if is_greeting else 'Subjective' if is_subjective else 'Technical'
            
            # NEW: Tab switches during THIS specific question
            q_tab_switches = TabSwitchEvent.objects.filter(
                session_id=session_id,
                question_id=r.question_id,
                event_type__in=['tab_hidden', 'window_blur']
            ).count()

            item = f"""
            Turn Type: {'Greeting' if is_greeting else 'Technical' if not is_subjective else 'Subjective'}
            Question: {r.question_text}
            User Answer: {r.user_answer}
            Best Matching Ideal Answer: {r.winning_ideal_answer or r.ideal_answer}
            Technical Similarity Score: {score:.2f}/1.0
            Detected Emotion: {r.dominant_emotion or 'N/A'} (Confidence: {r.emotion_confidence or 0:.0%})
            Posture Status: {r.posture_status or 'N/A'}
            Tab/Window Switches during this question: {q_tab_switches}
            Multiple Speaker Flags during this question: {r.multiple_speak_count}
            Multiple Face Flags during this question: {r.multiple_faces_count}
            -----------------------
            """
            interview_data.append(item)

        # ---------------------------------------------------------
        # 2. MULTIMODAL SCORING LOGIC (20% Weightage)
        # ---------------------------------------------------------
        # Multimodal scores (max 5 pts each, total 20)
        gesture_score = 0.0
        speaker_score = 0.0
        # 2.0 Tab Switch / Screen Activity (NEW: Cheat Detection)
        tab_switch_count = TabSwitchEvent.objects.filter(
            session_id=session_id, 
            event_type__in=['tab_hidden', 'window_blur']
        ).count()
        
        # 2.1 Body Gesture (5 pts)
        # Appropriate: 5, Defensive: 2.5, Cheating: 0
        from collections import Counter
        postures = [r.posture_status.lower() for r in responses if r.posture_status]
        
        if tab_switch_count > 0:
            # FORCE ZERO if ever switched tab or focus (as requested: "it shoukd give zero mark")
            gesture_score = 0.0
            dominant_gesture = "Cheating (Tab Switch Detected)"
            logger.warning(f"[FEEDBACK] Tab switch detected ({tab_switch_count}). Body posture score forced to 0.")
        elif postures:
            dominant_gesture = Counter(postures).most_common(1)[0][0]
            if "appropriate" in dominant_gesture: gesture_score = 5.0
            elif "defensive" in dominant_gesture: gesture_score = 2.5
            elif "cheating" in dominant_gesture: gesture_score = 0.0
            else: gesture_score = 4.0 # Default fallback
        else:
            dominant_gesture = "N/A"
            gesture_score = 5.0 # Baseline if no detections available
        
        # 2.2 Speaker Detection (5 pts)
        # 0-1 flags: 5, 2 flags: 2.5, >5: 0
        from detections.models import SpeakerDetection, FaceDetection
        speaker_flags = SpeakerDetection.objects.filter(session_id=session_id, is_multiple_speakers=True).count()
        if speaker_flags <= 1: speaker_score = 5.0
        elif speaker_flags == 2: speaker_score = 2.5
        elif speaker_flags > 5: speaker_score = 0.0
        else: speaker_score = 1.0 # Mid range
        
        # 2.3 Face Detection (5 pts)
        # 0 extra faces: 5, 1 detection: 4, >=2: 0
        face_flags = FaceDetection.objects.filter(session_id=session_id, face_count__gt=1).count()
        if face_flags == 0: face_score = 5.0
        elif face_flags == 1: face_score = 4.0
        else: face_score = 0.0
        
        # 2.4 Emotion Analysis (5 pts)
        # Professional/Neutral: 5, Negative: 2.5
        negative_emotions = ['angry', 'fear', 'disgust', 'sad']
        emotions = [r.dominant_emotion.lower() for r in responses if r.dominant_emotion]
        if emotions:
            neg_count = sum(1 for e in emotions if e in negative_emotions)
            if neg_count > len(emotions) / 2: emotion_score = 2.5
            else: emotion_score = 5.0

        multimodal_total = gesture_score + speaker_score + face_score + emotion_score
        
        full_transcript = "\n".join(interview_data)
        avg_tech_score = sum(technical_scores) / len(technical_scores) if technical_scores else 0
        
        num_tech_answered = len(technical_scores)
        
        # ---------------------------------------------------------
        # 3. HANDLE EMPTY INTERVIEW CASE
        # ---------------------------------------------------------
        if num_tech_answered == 0:
            logger.info(f"No technical questions answered for session {session_id}. Returning empty feedback message.")
            return Response({
                'success': True,
                'feedback': {
                    "score": 0,
                    "candidate_name": candidate_name,
                    "job_role": job_role,
                    "summary": "you should answer question to see your feedback report",
                    "question_breakdown": [],
                    "positives": [],
                    "negatives": []
                }
            })

        # ---------------------------------------------------------
        # 4. OVERALL FINAL SCORE CALCULATION
        # ---------------------------------------------------------
        # Weightage: 80% Technical Accuracy (Similarity), 20% Multimodal
        # avg_tech_score is 0-1. scaled to 80 max.
        
        # FIX: If only greeting was answered, give a baseline technical score so they don't get 0
        if not technical_scores and num_tech_answered == 0:
            final_sim_score = 40.0 # Baseline if no scorable questions answered yet
        else:
            final_sim_score = avg_tech_score * 80.0
            
        final_total_score = final_sim_score + multimodal_total
        final_total_score = max(10.0, min(100.0, final_total_score)) # Min 10 pts for participation
        
        # Build prompt safely
        prompt_intro = "Act as an expert interviewer. Review the session transcript and multimodal results.\n\n"
        prompt_data = "FULL TRANSCRIPT & MULTIMODAL DATA:\n" + full_transcript + "\n\n"
        prompt_speaker = f"SPEAKER DETECTION RESULTS: Flags={speaker_flags}, Score={speaker_score}/5.0\n"
        prompt_face = f"FACE DETECTION RESULTS: Flags={face_flags}, Score={face_score}/5.0\n"
        prompt_posture = f"POSTURE RESULTS: Dominant='{dominant_gesture if postures or tab_switch_count > 0 else 'N/A'}', Score={gesture_score}/5.0\n"
        if tab_switch_count > 0:
            prompt_posture += f"!!! CHEAT ALERT: Candidate switched tabs/windows {tab_switch_count} times. Posture score penalized to 0. !!!\n"
        prompt_emotion = f"EMOTION RESULTS: Score={emotion_score}/5.0\n\n"
        
        prompt_summary = (
            f"SUMMARY OF PRE-CALCULATED SCORES:\n"
            f"1. Technical Accuracy (SBERT): {avg_tech_score:.2f}/1.0 (Contribution: {final_sim_score:.1f}/80.0)\n"
            f"2. Multimodal Total: {multimodal_total:.1f}/20.0\n"
            f"   - Gesture/Posture: {gesture_score}/5.0\n"
            f"   - Speaker Verif: {speaker_score}/5.0\n"
            f"   - Face Verif: {face_score}/5.0\n"
            f"   - Emotion: {emotion_score}/5.0\n"
            f"3. FINAL SIMULATED SCORE: {final_total_score:.1f}/100.0\n\n"
        )
        
        prompt_instructions = (
            f"Provide a structured feedback report in JSON format. \n"
            f"IMPORTANT: Use the following scores as the basis for your evaluation: Overall Score={final_total_score:.0f}/100, Technical Accuracy={avg_tech_score:.2f}/1.0, Multimodal Score={multimodal_total:.1f}/20.0.\n"
            f"If the candidate answered fewer than 5 questions, only provide breakdown for those {num_tech_answered} questions present in the transcript.\n"
            "The JSON must have these keys:\n"
            f"- 'score': Use exactly the final total score provided ({final_total_score:.0f}).\n"
            f"- 'candidate_name': '{candidate_name}'\n"
            f"- 'job_role': '{job_role}'\n"
            "- 'summary': 2-3 sentence final summary of overall performance.\n"
            "- 'question_breakdown': A REQUIRED list of objects for ALL technical questions in the transcript:\n"
            "     {\n"
            "       'question_no': <int>,\n"
            "       'question': '<text>',\n"
            "       'user_answer': '<text>',\n"
            "       'ideal_answer': '<The Best Matching Ideal Answer variant provided in transcript>',\n"
            "       'metrics': {\n"
            "         'semantic_score': <float (0-1.0)>,\n"
            "         'posture': '<text>',\n"
            "         'emotion': '<text>',\n"
            "         'speaker_flags': <int>,\n"
            "         'face_flags': <int>\n"
            "       },\n"
            "       'positives': ['Bullet point 1', 'Bullet point 2'],\n"
            "       'negatives': ['Bullet point 1', 'Bullet point 2']\n"
            "     }\n"
            "  DO NOT skip the question_breakdown. Include every technical question answered.\n"
            "- 'positives': Overall session positives (3-4).\n"
            "- 'negatives': Overall session areas for improvement (3-4).\n\n"
            "Output ONLY valid JSON."
        )
        
        prompt = prompt_intro + prompt_data + prompt_speaker + prompt_face + prompt_posture + prompt_emotion + prompt_summary + prompt_instructions
        
        gemini_service = GeminiService()
        result = gemini_service.generate_text(prompt, temperature=0.7)
        
        # ---------------------------------------------------------
        # 4. PARSE OR FALLBACK
        # ---------------------------------------------------------
        # Create a solid fallback breakdown from DB content
        fallback_breakdown = []
        for i, r in enumerate(responses):
            if r.user_answer and r.question_id != 'GREETING':
                # Tab switches for this response
                resp_tab_switches = TabSwitchEvent.objects.filter(
                    session_id=session_id,
                    question_id=r.question_id,
                    event_type__in=['tab_hidden', 'window_blur']
                ).count()
                
                fallback_breakdown.append({
                    "question_no": len(fallback_breakdown) + 1,
                    "question": r.question_text,
                    "user_answer": r.user_answer,
                    "ideal_answer": r.winning_ideal_answer or r.ideal_answer or "N/A",
                    "metrics": {
                        "semantic_score": r.similarity_score or 0.0,
                        "posture": "Cheating (Tab Switch)" if resp_tab_switches > 0 else (r.posture_status or "N/A"),
                        "emotion": r.dominant_emotion or "N/A",
                        "speaker_flags": r.multiple_speak_count,
                        "face_flags": r.multiple_faces_count,
                        "tab_switches": resp_tab_switches
                    },
                    "positives": ["Response successfully recorded."],
                    "negatives": ["Detailed AI analysis pending."]
                })

        import json
        import re
        feedback_json = None

        if result.get('success'):
            try:
                content = result['text']
                clean_content = content.replace('```json', '').replace('```', '').strip()
                json_match = re.search(r'\{.*\}', clean_content, re.DOTALL)
                if json_match:
                    clean_content = json_match.group(0)
                feedback_json = json.loads(clean_content)
                
                # Check structure
                if not feedback_json.get('question_breakdown'):
                    feedback_json['question_breakdown'] = fallback_breakdown

            except Exception as json_err:
                logger.error(f"JSON Parse Error for Feedback: {json_err}")
                feedback_json = None

        if not feedback_json:
            # Full Fallback if Gemini failed or JSON invalid
            logger.warning("Using FALLBACK feedback report due to AI failure.")
            feedback_json = {
                "score": int(final_total_score),
                "candidate_name": candidate_name,
                "job_role": job_role,
                "summary": f"Interview session completed. Overall score calculation: {final_total_score:.0f}/100. (AI detailed analysis unavailable)",
                "question_breakdown": fallback_breakdown,
                "positives": ["Detailed technical responses recorded.", "Professional demeanor maintained throughout session."],
                "negatives": ["AI detailed analysis temporarily unavailable.", "Feedback based on semantic matching scores."]
            }
        
        # ALWAYS override/inject critical metadata to ensure UI shows it
        feedback_json['candidate_name'] = candidate_name
        feedback_json['job_role'] = job_role
        feedback_json['tab_switch_count'] = tab_switch_count
        
        # ── CRITICAL FIX: Build a DB lookup map for all per-question scores ──
        # Gemini may report 0 or wrong semantic_score in its generated JSON.
        # We ALWAYS override it with the real SBERT score stored in the database.
        db_score_map = {}  # question_text (lower) -> similarity_score
        db_ideal_map = {}  # question_text (lower) -> winning_ideal_answer
        for r in responses:
            if r.question_text and r.question_id != 'GREETING':
                key = r.question_text.strip().lower()
                db_score_map[key] = r.similarity_score if r.similarity_score is not None else 0.0
                db_ideal_map[key] = r.winning_ideal_answer or r.ideal_answer or "N/A"

        for item in feedback_json.get('question_breakdown', []):
            q_text_key = (item.get('question') or '').strip().lower()

            # 1) Always inject the real SBERT score from DB (fix Gemini reporting 0)
            if q_text_key in db_score_map:
                if 'metrics' not in item or not isinstance(item.get('metrics'), dict):
                    item['metrics'] = {}
                real_score = db_score_map[q_text_key]
                item['metrics']['semantic_score'] = real_score
                logger.info(f"[FEEDBACK] Injected real SBERT score {real_score:.4f} for: '{item.get('question', '')[:60]}'")

            # 3) Inject Tab Switch Count - Prioritize DB stored value if found
            q_tab_count = 0
            # Try to fetch from stored user response first (pre-calculated during save)
            for r in responses:
                if r.question_text and r.question_text.strip().lower() == q_text_key:
                    q_tab_count = r.tab_switch_count or 0
                    curr_q_id = r.question_id
                    break
            
            # Fallback to direct event query if DB value is 0 (double check)
            if q_tab_count == 0 and curr_q_id:
                q_tab_count = TabSwitchEvent.objects.filter(
                    session_id=session_id,
                    question_id=curr_q_id,
                    event_type__in=['tab_hidden', 'window_blur']
                ).count()
            
            item['metrics']['tab_switches'] = q_tab_count
            if q_tab_count > 0:
                item['metrics']['posture'] = f"Warning (Tab Switch x{q_tab_count})" if q_tab_count < 3 else "Cheating (Multiple Switches)"

            # 4) Ensure ideal_answer is correct
            if not item.get('ideal_answer') or item.get('ideal_answer') in ["None", "N/A", ""]:
                if q_text_key in db_ideal_map:
                    item['ideal_answer'] = db_ideal_map[q_text_key]
                else:
                    # Fallback: filter by question text
                    resp_item = responses.filter(question_text=item.get('question')).first()
                    if resp_item:
                        item['ideal_answer'] = resp_item.winning_ideal_answer or resp_item.ideal_answer or "Evaluation Pending"

        return Response({
            'success': True,
            'feedback': feedback_json
        })

    except Exception as e:
        logger.error(f"Feedback generation error for session {session_id}: {str(e)}")
        # Check for Quota Exceeded specifically
        if "429" in str(e) or "quota" in str(e).lower():
            logger.critical("GEMINI QUOTA EXCEEDED during feedback generation.")
            return Response({
                'error': 'Gemini AI Quota Exceeded. Please try again in a few minutes or check billing.',
                'details': 'QUOTA_EXCEEDED'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
        return Response({
            'error': f'Feedback generation failed: {str(e)}',
            'details': 'INTERNAL_SERVER_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def get_feedback_report_api(request, session_id=None):
    """
    Alias or wrapper for fetching/generating feedback report.
    Supports both GET (with session_id in URL or query params) and POST (with session_id in body).
    """
    if not session_id:
        session_id = request.query_params.get('session_id')
        
    return generate_feedback_report_api(request, session_id=session_id)


@api_view(['POST'])
@permission_classes([AllowAny])
def refine_transcript_api(request):
    """
    Refine a raw speech-to-text transcript using Gemini (Quillbot-style).
    """
    try:
        text = request.data.get('text')
        if not text:
            return Response({'error': 'text is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        prompt = (
            f"Please refine the following raw speech-to-text transcript to be grammatically correct, "
            f"smooth, and professional, while preserving the original meaning exactly. "
            f"Do not add any preamble or extra text. Output ONLY the refined version.\n\n"
            f"Raw text: \"{text}\""
        )
        
        gemini_service = GeminiService()
        result = gemini_service.generate_text(prompt, temperature=0.3)
        
        if result.get('success'):
            refined_text = result['text'].strip()
            # Remove any quotes if Gemini added them
            if refined_text.startswith('"') and refined_text.endswith('"'):
                refined_text = refined_text[1:-1]
            return Response({'refined_text': refined_text})
        else:
             return Response({'error': 'Gemini refinement failed', 'details': result.get('error')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        logger.error(f"Transcript refinement error: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def end_interview_api(request):
    """
    API endpoint to end the interview session
    """
    try:
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({'error': 'session_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Fetch session
        try:
            conversation = GeminiConversation.objects.get(session_id=session_id)
            conversation.is_active = False
            conversation.save()
            return Response({'success': True, 'message': 'Interview ended successfully'})
        except GeminiConversation.DoesNotExist:
             return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error(f"Error ending interview: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def tts_api(request):
    """
    API endpoint to convert text to speech using edge-tts.
    """
    text = request.query_params.get('text')
    if not text:
        return Response({'error': 'Text parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Since this is a Django view (synchronous), we need to run the async tts function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        filepath = loop.run_until_complete(generate_speech(text))
        loop.close()
        
        return FileResponse(open(filepath, 'rb'), content_type='audio/mpeg')
    except Exception as e:
        logger.error(f"TTS Error: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
