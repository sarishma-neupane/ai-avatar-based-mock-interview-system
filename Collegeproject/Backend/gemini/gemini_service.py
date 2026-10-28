"""
Gemini API Service
Handles all interactions with Google Gemini API
"""
import os
import time
import logging
from typing import Dict, List, Optional, Any
from decouple import config
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Configure Gemini API
GEMINI_API_KEY = config('GEMINI_API_KEY', default='')
GEMINI_MODEL = config('GEMINI_MODEL', default='gemini-2.5-flash-lite')

# Initialize Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not found in environment variables")


class GeminiService:
    """Service class for interacting with Google Gemini API"""
    
    def __init__(self, model_name: str = None):
        """
        Initialize Gemini service
        
        Args:
            model_name: Name of the Gemini model to use (default: from env or 'gemini-2.5-flash-lite')
        """
        self.model_name = model_name or GEMINI_MODEL
        # Ensure model name doesn't have 'models/' prefix (it's added automatically)
        if self.model_name.startswith('models/'):
            self.model_name = self.model_name.replace('models/', '')
        self.api_key = GEMINI_API_KEY
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured. Please set it in your .env file.")
        
        try:
            self.model = genai.GenerativeModel(self.model_name)
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {str(e)}")
            raise
    
    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate text using Gemini API
        
        Args:
            prompt: The user prompt
            system_instruction: Optional system instruction
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional generation parameters
        
        Returns:
            Dictionary with 'text', 'tokens_used', 'response_time_ms', and 'success'
        """
        start_time = time.time()
        
        try:
            generation_config = {
                'temperature': temperature,
                **kwargs
            }
            
            if max_tokens:
                generation_config['max_output_tokens'] = max_tokens
            
            # Build the full prompt
            full_prompt = prompt
            if system_instruction:
                full_prompt = f"{system_instruction}\n\n{prompt}"
            
            # Generate response
            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Extract response text
            response_text = response.text if hasattr(response, 'text') else str(response)
            
            # Get token usage if available
            tokens_used = 0
            if hasattr(response, 'usage_metadata'):
                tokens_used = getattr(response.usage_metadata, 'total_token_count', 0)
            
            return {
                'text': response_text,
                'tokens_used': tokens_used,
                'response_time_ms': response_time_ms,
                'success': True,
                'raw_response': response
            }
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Gemini API error: {str(e)}")
            if "429" in str(e) or "ResourceExhausted" in str(e) or "Quota exceeded" in str(e):
                print(f"\n{'!'*20} GEMINI QUOTA EXCEEDED {'!'*20}")
                print(f"Error: {e}")
                print("Your API key has hit the free tier limit for this model.")
                print("SUGGESTION: Switch to 'gemini-1.5-flash' in your .env file or Backend/gemini/gemini_service.py")
                print(f"{'!'*60}\n")

            return {
                'text': None,
                'tokens_used': 0,
                'response_time_ms': response_time_ms,
                'success': False,
                'error': str(e)
            }
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Chat with Gemini using conversation history
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
                     Example: [{'role': 'user', 'content': 'Hello'}, ...]
            system_instruction: Optional system instruction
            temperature: Sampling temperature
            **kwargs: Additional generation parameters
        
        Returns:
            Dictionary with response data
        """
        start_time = time.time()
        
        try:
            # Start a chat session
            chat = self.model.start_chat(history=[])
            
            # Add system instruction if provided
            if system_instruction:
                # For Gemini, we include system instruction in the first user message
                if messages and messages[0]['role'] == 'user':
                    messages[0]['content'] = f"{system_instruction}\n\n{messages[0]['content']}"
            
            # Send messages in sequence
            last_response = None
            for message in messages:
                if message['role'] == 'user':
                    last_response = chat.send_message(
                        message['content'],
                        generation_config={
                            'temperature': temperature,
                            **kwargs
                        }
                    )
                # Note: Gemini chat handles assistant responses automatically
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Extract response
            response_text = last_response.text if last_response and hasattr(last_response, 'text') else ""
            
            # Get token usage
            tokens_used = 0
            if last_response and hasattr(last_response, 'usage_metadata'):
                tokens_used = getattr(last_response.usage_metadata, 'total_token_count', 0)
            
            return {
                'text': response_text,
                'tokens_used': tokens_used,
                'response_time_ms': response_time_ms,
                'success': True,
                'raw_response': last_response
            }
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Gemini chat error: {str(e)}")
            if "429" in str(e) or "ResourceExhausted" in str(e) or "Quota exceeded" in str(e):
                 print(f"\n{'!'*20} GEMINI QUOTA EXCEEDED {'!'*20}")
                 print("Your API key has hit the request limit.")

            return {
                'text': None,
                'tokens_used': 0,
                'response_time_ms': response_time_ms,
                'success': False,
                'error': str(e)
            }
    
    def generate_interview_questions(
        self,
        job_role: str,
        years_of_experience: str,
        candidate_name: Optional[str] = None,
        candidate_background: Optional[str] = None,
        skills: Optional[List[str]] = None,
        question_types: Optional[List[str]] = None,
        include_ideal_answers: bool = True,
        focus_areas: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate interview questions for a specific job role with ideal answers
        Following the new AI Interview Assistant format
        
        Args:
            job_role: The job role/position
            years_of_experience: Years of experience
            candidate_name: Optional candidate name
            candidate_background: Optional candidate background information
            skills: Optional list of candidate skills
            question_count: Number of questions to generate
            question_types: Optional list of question types (e.g., ['technical', 'behavioral'])
            include_ideal_answers: Whether to generate ideal answers (default: True)
        
        Returns:
            Dictionary with generated questions and ideal answers in the new format
        """
        import uuid
        import json
        import time as time_module
        
        start_time = time_module.time()
        
        # PART 1: Generate Interview Questions
        system_instruction = """You are HIMANI, a professional AI Interviewer.
Your task is to:
2. Generate exactly 5 relevant technical or subjective questions for the specified Job Role, Experience level, and selected Focus Areas.

RULES:
- Return ONLY valid JSON.
- The questions MUST STRICTLY focus on the provided "Focus Areas" if specified. Do not ask general questions outside these areas.
- BE CREATIVE AND DIVERSE: Avoid asking the most common/cliche questions. Draw from a wide pool of technical topics within the focus area.
- UNIFORMITY AVOIDANCE: Each time you are called, generate a different set of questions than what might be considered "standard".
- The first item in the "questions" list MUST be the greeting (question_id: "GREETING").
- Subsequent 5 items must be technical questions (question_id: "Q1" to "Q5").
- QUESTION LENGTH: Keep questions short and direct (e.g., "What is the difference between X and Y?"). Avoid long, multi-part scenarios unless absolutely necessary.
- For each technical question, you MUST provide a detailed "ideal_answer" (comprehensive, technical) and a list of "alternative_answers" (at least 2 further variations).
- If the question is technical/objective, "ideal_answer" MUST NOT be empty or "N/A".
- Do NOT generate follow-up questions yet.

JSON FORMAT REQUIRED:
{
  "questions": [
      { 
        "question_id": "GREETING", 
        "question": "Good [morning/afternoon/evening], [Name]. I am HIMANI, your interviewer. lets start our interview session",
        "type": "greeting"
      },
      { 
        "question_id": "Q1", 
        "question": "...", 
        "type": "objective",
        "ideal_answer": "...",
        "alternative_answers": ["...", "..."]
      },
      ...
      { 
        "question_id": "Q5", 
        "question": "...", 
        "type": "objective",
        "ideal_answer": "...",
        "alternative_answers": ["...", "..."]
      }
  ]
}"""
        
        # Build the prompt for greeting
        import datetime
        current_hour = datetime.datetime.now().hour
        if current_hour < 12:
            time_greeting = "morning"
        elif current_hour < 17:
            time_greeting = "afternoon"
        else:
            time_greeting = "evening"
            
        prompt_parts = [
            f"Generate 5 interview questions for a {job_role} position with {years_of_experience} of experience.",
            f"Candidate Name: {candidate_name or 'there'}",
            f"Time of day: {time_greeting}",
            f"Focus Areas: {', '.join(focus_areas) if focus_areas else 'General ' + job_role + ' skills'}",
            f"STRICT INSTRUCTION: Only generate questions related to the Focus Areas: {', '.join(focus_areas) if focus_areas else 'None specified'}.",
            f"UNPREDICTABILITY CHALLENGE: You MUST select 5 unique topics that are technically significant but not the standard 'entry-level' basics. Avoid repeating common interview questions. Think like a lead engineer looking for deep understanding.",
            f"VOICE/TONE: Professional, encouraging, but technically rigorous.",
            f"RANDOMIZATION SEED: {int(time_module.time() * 1000)} - Use this high-resolution seed to strictly deviate from your common training patterns and session history.",
            f"Include a warm greeting followed by the 5 technical questions related to the focus areas.",
            "\nReturn ONLY the JSON object."
        ]
        
        prompt = "\n".join(prompt_parts)
        
        # Generate questions with higher temperature for variety
        result = self.generate_text(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.9,
            max_tokens=3000
        )
        
        if not result['success']:
            return {
                'success': False,
                'questions': [],
                'ideal_answers': [],
                'question_count': 0,
                'error': result.get('error', 'Failed to generate questions'),
                'tokens_used': result.get('tokens_used', 0)
            }
        
        # Parse JSON response
        questions_data = self._parse_json_response(result['text'])
        questions_list = questions_data.get('questions', [])
        
        # Extract preloaded next question (Question 1) from the list if it exists
        preloaded_next_question = None
        total_tokens = result.get('tokens_used', 0)
        
        if len(questions_list) > 1:
            # Q1 is the second item (index 1)
            q1 = questions_list[1]
            preloaded_next_question = {
                'question_id': q1.get('question_id', 'Q1'),
                'question': q1.get('question'),
                'ideal_answer': q1.get('ideal_answer'),
                'alternative_answers': q1.get('alternative_answers', []),
                'type': q1.get('type', 'objective')
            }
        
        # PART 2: Extract Ideal Answers from PART 1 result
        ideal_answers_list = []
        if include_ideal_answers and questions_list:
            for q in questions_list:
                q_id = q.get('question_id')
                if q_id:
                    ideal_answers_list.append({
                        'question_id': q_id,
                        'ideal_answer': q.get('ideal_answer', ''),
                        'alternative_answers': q.get('alternative_answers', [])
                    })
        
        overall_duration = (time.time() - start_time)
        logger.info(f"generate_interview_questions COMPLETED in {overall_duration:.2f}s (Total tokens: {total_tokens})")
        
        return {
            'success': True,
            'questions': questions_list,
            'preloaded_next_question': preloaded_next_question,
            'ideal_answers': ideal_answers_list,
            'question_count': len(questions_list),
            'tokens_used': total_tokens,
            'response_time_ms': result.get('response_time_ms', 0)
        }
    
    def _generate_ideal_answer_with_alternatives(
        self,
        question: str,
        question_id: str,
        job_role: str,
        years_of_experience: str
    ) -> Dict[str, Any]:
        """
        Generate an ideal answer with alternative answers for a specific interview question
        
        Args:
            question: The interview question
            question_id: The unique question ID
            job_role: The job role/position
            years_of_experience: Years of experience
        
        Returns:
            Dictionary with ideal_answer and alternative_answers
        """
        import json
        
        system_instruction = """You are an expert interview coach. 
For each interview question, generate:
- A perfect, well-structured ideal answer
- Consider ALL possible correct variations that candidates may answer
- If the answer has multiple valid options, mention all of them
- Answers should be concise, professional, and technically correct

You MUST return ONLY valid JSON in this exact format:
{
  "ideal_answer": "<best possible answer>",
  "alternative_answers": ["<option_1>", "<option_2>", "..."]
}

If there are no meaningful alternatives, return an empty array for alternative_answers."""
        
        prompt = f"""Generate an ideal answer for the following interview question:

Question: {question}

Job Role: {job_role}
Experience Level: {years_of_experience}

Provide:
1. The best possible ideal answer (concise, professional, technically correct)
2. Alternative valid answers if there are multiple correct approaches or valid responses

Return ONLY the JSON object. Do not include any other text."""
        
        result = self.generate_text(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.7,
            max_tokens=2000
        )
        
        if not result.get('success'):
            return {
                'success': False,
                'ideal_answer': '',
                'alternative_answers': [],
                'tokens_used': result.get('tokens_used', 0),
                'error': result.get('error')
            }
        
        # Parse JSON response
        answer_data = self._parse_json_response(result['text'])
        
        return {
            'success': True,
            'ideal_answer': answer_data.get('ideal_answer', ''),
            'alternative_answers': answer_data.get('alternative_answers', []),
            'tokens_used': result.get('tokens_used', 0)
        }
    
    def process_user_response(
        self,
        question_id: str,
        question: str,
        user_response: str,
        job_role: str,
        years_of_experience: str,
        candidate_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process user response and generate follow-up questions if needed
        
        Args:
            question_id: The original question ID
            question: The original question text
            user_response: The user's spoken or typed answer
            job_role: The job role/position
            years_of_experience: Years of experience
            candidate_name: Optional candidate name
        
        Returns:
            Dictionary with follow-up information
        """
        import json
        
        system_instruction = """You are an AI Interview Assistant analyzing candidate responses.
When a user provides their spoken or typed answer:
- Analyze the answer deeply
- If the answer requires more detail or clarification:
    • Generate a follow-up question related to the SAME original question
    • Provide an ideal answer + alternative answers for the follow-up as well
- If no follow-up is required, return "follow_up_required": false

You MUST return ONLY valid JSON in this exact format:
{
  "follow_up": {
      "follow_up_required": true/false,
      "question": "<follow-up question if needed>",
      "ideal_answer": "<best possible ideal response>",
      "alternative_answers": ["<option_1>", "<option_2>", "..."]
  }
}

If follow_up_required is false, the question, ideal_answer, and alternative_answers fields can be empty strings/arrays."""
        
        prompt_parts = [
            f"Original Question ID: {question_id}",
            f"Original Question: {question}",
            f"User Response: {user_response}",
            "",
            f"Job Role: {job_role}",
            f"Experience Level: {years_of_experience}",
        ]
        
        if candidate_name:
            prompt_parts.append(f"Candidate Name: {candidate_name}")
        
        prompt_parts.append("\nAnalyze the user's response and determine if a follow-up question is needed.")
        prompt_parts.append("If the answer is incomplete, vague, or needs clarification, generate a follow-up.")
        prompt_parts.append("If the answer is sufficient and complete, set follow_up_required to false.")
        prompt_parts.append("\nReturn ONLY the JSON object. Do not include any other text.")
        
        prompt = "\n".join(prompt_parts)
        
        result = self.generate_text(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.7,
            max_tokens=2000
        )
        
        if not result.get('success'):
            return {
                'success': False,
                'follow_up': {
                    'follow_up_required': False,
                    'question': '',
                    'ideal_answer': '',
                    'alternative_answers': []
                },
                'error': result.get('error', 'Failed to process response'),
                'tokens_used': result.get('tokens_used', 0)
            }
        
        # Parse JSON response
        response_data = self._parse_json_response(result['text'])
        follow_up_data = response_data.get('follow_up', {})
        
        return {
            'success': True,
            'follow_up': {
                'follow_up_required': follow_up_data.get('follow_up_required', False),
                'question': follow_up_data.get('question', ''),
                'ideal_answer': follow_up_data.get('ideal_answer', ''),
                'alternative_answers': follow_up_data.get('alternative_answers', [])
            },
            'tokens_used': result.get('tokens_used', 0),
            'response_time_ms': result.get('response_time_ms', 0)
        }

    def generate_explicit_followup(
        self,
        current_question: str,
        current_answer: str,
        job_role: str,
        years_of_experience: str,
        question_id: str
    ) -> Dict[str, Any]:
        """
        Forcefully generate a follow-up question when the user's answer is weak (<.6 similarity).
        """
        import uuid
        
        system_instruction = f"""You are an expert technical interviewer for a {job_role} position ({years_of_experience}). 
The candidate provided a weak or incomplete answer to the previous question.
Your task is to ask a specific follow-up question to probe their understanding deeper or ask for clarification.
The follow-up should be directly related to the previous question.

Input Context:
Previous Question: "{current_question}"
Candidate Answer: "{current_answer}"

You MUST return ONLY valid JSON in this exact format:
{{
  "question": "<The follow-up question>",
  "ideal_answer": "<The comprehensive ideal answer for this follow-up>",
  "alternative_answers": ["<alt1>", "<alt2>"],
  "question_id": "FOLLOWUP_{str(uuid.uuid4())}",
  "type": "followup"
}}
"""
        prompt = "Generate the follow-up question now based on the input."
        
        result = self.generate_text(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.7
        )
        
        if not result['success']:
            return {'success': False, 'error': result['error']}
            
        data = self._parse_json_response(result['text'])
        data['success'] = True
        return data

    def generate_next_question(
        self,
        job_role: str,
        years_of_experience: str,
        current_question: str,
        current_answer: str,
        last_question_id: str = 'unknown',
        previous_history: List[Dict[str, str]] = None,
        candidate_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate the NEXT interview question based on the user's answer to the current question.
        
        Args:
            job_role: Job role
            years_of_experience: Experience
            current_question: The question just asked
            current_answer: The user's answer
            previous_history: List of {question: ..., answer: ...} for context (optional)
        
        Returns:
            Dict with 'question', 'ideal_answer', 'alternative_answers', 'question_id'
        """
        # The session turn limit is now handled by views.py
        import uuid
        
        questions_asked = len(previous_history) if previous_history else 0
        is_first_question = (questions_asked == 0) and (last_question_id == 'GREETING' or last_question_id == 'unknown')
        
        system_instruction = f"""You are HIMANI, an expert AI Technical Interviewer for a {job_role} position ({years_of_experience}).
Your goal is to assess the candidate's skills through a structured interview.

Context:
- Current Question: "{current_question}"
- Candidate Answer: "{current_answer}"
- Questions Asked So Far: {questions_asked}
- Target Total Questions: 5

RULES FOR QUESTION GENERATION:
1. You MUST generate exactly 5 scorable questions in total for the session.
2. Question 1 (if this is it) can be Technical or a Subjective Icebreaker.
3. For Questions 2-5:
   - If the previous answer was very strong (detailed, accurate, similarity > 0.6), you can ask a challenging FOLLOW-UP question on the same topic to probe deeper.
   - Otherwise, move to a NEW topic or question related to {job_role}.
4. Do NOT repeat any questions or topics already discussed.
5. Provide a clear "ideal_answer" for scorable questions.

You MUST return ONLY valid JSON in this exact format:
{{
  "question": "<your new question>",
  "ideal_answer": "<ideal answer or 'Subjective - No Evaluation' if it is an icebreaker>", 
  "alternative_answers": ["<alt1>", "<alt2>"],
  "question_id": "{str(uuid.uuid4())}",
  "type": "objective" (or "subjective" if it is an icebreaker)
}}
"""

        # Update system instruction with current progress
        
        prompt = f"Generate the next question for the {job_role} candidate."
        
        result = self.generate_text(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.7,
            max_tokens=1000
        )
        
        if not result['success']:
             # Fallback
             return {
                 'success': False, 
                 'error': result.get('error'),
                 'question': "Could you explain your experience with the core technologies in your resume?",
                 'question_id': str(uuid.uuid4()),
                 'ideal_answer': "Candidate should list their skills.",
                 'type': 'objective',
                 'alternative_answers': []
             }
             
        parsed = self._parse_json_response(result['text'])
        parsed['success'] = True
        parsed['tokens_used'] = result.get('tokens_used', 0)
        
        # Ensure question text exists
        if not parsed.get('question'):
            parsed['question'] = "Could you tell me more about your technical experience and projects you have worked on?"
            parsed['type'] = 'objective'
            parsed['ideal_answer'] = "Candidate should describe their projects and experience."

        # Ensure ID exists
        if 'question_id' not in parsed:
            parsed['question_id'] = str(uuid.uuid4())
            
        return parsed
    
    def generate_question_feedback(
        self,
        question: str,
        user_answer: str,
        ideal_answer: str,
        similarity_score: float,
        emotion_data: Optional[Dict[str, Any]] = None,
        posture_data: Optional[str] = None,
        job_role: str = "Software Engineer",
        years_of_experience: str = "3 years"
    ) -> Dict[str, Any]:
        """
        Generate detailed feedback (positives and negatives) for a specific question-answer pair
        
        Args:
            question: The interview question
            user_answer: The candidate's response
            ideal_answer: The expected answer
            similarity_score: SBERT semantic similarity score (0-1.0)
            emotion_data: Dict with 'emotion' and 'confidence' keys
            posture_data: Posture status string
            job_role: For context
            years_of_experience: For context
        
        Returns:
            Dictionary with 'success', 'positives', 'negatives', 'tokens_used'
        """
        import json
        
        # Extract emotion info
        emotion = emotion_data.get('emotion', 'neutral') if emotion_data else 'neutral'
        emotion_confidence = emotion_data.get('confidence', 0.0) if emotion_data else 0.0
        posture_status = posture_data or 'unknown'
        
        system_instruction = """You are an expert interview coach analyzing a candidate's response.

Your task is to provide SPECIFIC, ACTIONABLE feedback based on the candidate's answer and performance metrics.

RULES:
1. Provide 2-3 specific positives (what they did well)
2. Provide 2-3 specific negatives (areas for improvement)
3. Be SPECIFIC - reference actual content from their answer
4. Avoid generic feedback like "Good job" or "Needs improvement"
5. Consider all metrics: semantic accuracy, communication style, confidence

Return ONLY valid JSON in this format:
{
  "positives": ["Specific positive 1", "Specific positive 2", "..."],
  "negatives": ["Specific improvement 1", "Specific improvement 2", "..."]
}
"""
        
        prompt = f"""Analyze this interview response:

**Question**: {question}

**Ideal Answer**: {ideal_answer}

**Candidate's Answer**: {user_answer}

**Performance Metrics**:
- Semantic Similarity: {similarity_score:.2f}/1.0 (Content accuracy)
- Emotion Detected: {emotion} (Confidence: {emotion_confidence:.0%})
- Posture Status: {posture_status}
- Job Role: {job_role} ({years_of_experience})

**Instructions**:
1. Identify 2-3 KEY POSITIVES from their answer (be specific, reference their actual words/concepts)
2. Identify 2-3 KEY NEGATIVES or areas for improvement (be specific and actionable)

Consider:
- Technical accuracy (similarity score)
- Completeness of answer
- Communication clarity
- Confidence level (emotion + posture)
- Missing key concepts from ideal answer

Return ONLY the JSON object."""

        result = self.generate_text(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.7,
            max_tokens=800
        )
        
        if not result.get('success'):
            return {
                'success': False,
                'positives': [],
                'negatives': [],
                'tokens_used': result.get('tokens_used', 0),
                'error': result.get('error', 'Failed to generate feedback')
            }
        
        # Parse JSON response
        feedback_data = self._parse_json_response(result['text'])
        
        return {
            'success': True,
            'positives': feedback_data.get('positives', []),
            'negatives': feedback_data.get('negatives', []),
            'tokens_used': result.get('tokens_used', 0)
        }
    
    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """
        Parse JSON from Gemini response text
        Handles cases where response may have markdown code blocks or extra text
        
        Args:
            text: Response text from Gemini
        
        Returns:
            Parsed JSON dictionary
        """
        import json
        import re
        
        if not text:
            return {}
        
        # Remove markdown code blocks if present
        text = text.strip()
        
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        else:
            # Try to find JSON object in the text
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                text = json_match.group(0)
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.error(f"Response text: {text[:500]}")
            return {}
    
    def _parse_questions_from_text(self, text: str) -> List[str]:
        """
        Parse questions from Gemini response text (legacy method, kept for backward compatibility)
        
        Args:
            text: Response text from Gemini
        
        Returns:
            List of question strings
        """
        if not text:
            return []
        
        questions = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove numbering (1., 2., etc.) or bullet points
            line = line.lstrip('0123456789.-) ')
            
            # Check if it looks like a question
            if line and ('?' in line or len(line) > 20):
                questions.append(line)
        
        return questions if questions else [text]  # Fallback to full text if parsing fails

    def calculate_semantic_similarity_llm(self, user_answer: str, ideal_texts: List[str], question_text: str = "") -> Dict[str, Any]:
        """
        Fallback method: Use Gemini to calculate semantic similarity when SBERT is unavailable.
        """
        import json
        
        system_instruction = """You are a technical evaluation engine. Your goal is to compare a candidate's answer against a set of ideal reference answers.
        
        Evaluate the semantic similarity on a scale of 0.0 to 1.0.
        Criteria:
        - 1.0: Perfect technical match, covers all key points.
        - 0.8: Good match, minor omissions.
        - 0.5: Partial understanding, missing core components.
        - 0.2: Vague or barely related.
        - 0.0: Irrelevant, incorrect, or "I don't know".
        
        If the 'question_text' is provided and the 'user_answer' is just a rephrasing or echo of the question without providing an actual answer, the score MUST be 0.0.
        
        Return ONLY valid JSON:
        {
          "score": <float between 0.0 and 1.0>,
          "best_match": "<the text from ideal_texts that matched best>",
          "reasoning": "<short explanation>"
        }
        """
        
        ideal_content = "\n".join([f"- {t}" for t in ideal_texts[:3]]) # Limit to top 3 for prompt context
        
        prompt = f"""
        Question asked: {question_text}
        Candidate's Answer: {user_answer}
        
        Reference Ideal Answers:
        {ideal_content}
        
        Evaluate the Candidate's Answer now.
        """
        
        try:
            result = self.generate_text(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.0, # Neutral/Precise
            )
            
            if not result['success']:
                return {'score': 0.0, 'best_match': ideal_texts[0] if ideal_texts else ""}
                
            data = self._parse_json_response(result['text'])
            # Ensure score is a float and within bounds
            data['score'] = max(0.0, min(1.0, float(data.get('score', 0.0))))
            return data
        except Exception as e:
            logger.error(f"Error in Gemini similarity fallback: {e}")
            return {'score': 0.0, 'best_match': ideal_texts[0] if ideal_texts else ""}


