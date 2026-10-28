/**
 * Gemini API Service
 * Handles all API calls to backend Gemini endpoints
 */
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

/**
 * Helper function to validate and get token
 * Returns null if token is invalid or empty
 */
const getValidToken = () => {
  const token = localStorage.getItem('token');
  if (!token || token.trim() === '' || token === 'null' || token === 'undefined') {
    return null;
  }

  // Basic JWT format validation (3 parts separated by dots)
  try {
    const parts = token.split('.');
    if (parts.length === 3 && parts[0] && parts[1] && parts[2]) {
      // Additional validation: check if token payload is valid and not expired
      try {
        const payload = JSON.parse(atob(parts[1]));
        // Check if token is expired (if exp field exists)
        if (payload.exp && payload.exp < Date.now() / 1000) {
          console.log('Token expired, clearing...');
          localStorage.removeItem('token');
          localStorage.removeItem('refreshToken');
          return null;
        }
        return token;
      } catch {
        // Invalid payload, clear token
        console.log('Invalid token payload, clearing...');
        localStorage.removeItem('token');
        localStorage.removeItem('refreshToken');
        return null;
      }
    } else {
      // Invalid format
      console.log('Invalid token format, clearing...');
      localStorage.removeItem('token');
      localStorage.removeItem('refreshToken');
      return null;
    }
  } catch (e) {
    // Invalid format
    localStorage.removeItem('token');
    localStorage.removeItem('refreshToken');
    return null;
  }
};

/**
 * Helper function to build headers with optional auth
 */
const buildHeaders = () => {
  const headers = {
    'Content-Type': 'application/json',
  };

  const token = getValidToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
};

/**
 * Generate interview questions using Gemini
 * @param {Object} params - Question generation parameters
 * @param {string} params.jobRole - Job role/position
 * @param {string} params.yearsOfExperience - Years of experience
 * @param {string} [params.candidateName] - Optional candidate name
 * @param {number} [params.questionCount] - Number of questions to generate (default from env or 5)
 * @param {string} [params.sessionId] - Optional session ID
 * @returns {Promise<Object>} Response with questions
 */
export const generateInterviewQuestions = async ({
  jobRole,
  yearsOfExperience,
  candidateName = null,
  questionCount = null,
  sessionId = null,
  focusAreas = []
}) => {
  // Clear any invalid tokens first
  const token = localStorage.getItem('token');
  if (token) {
    try {
      const parts = token.split('.');
      if (parts.length !== 3) {
        localStorage.removeItem('token');
        localStorage.removeItem('refreshToken');
      } else {
        // Check if token is expired
        try {
          const payload = JSON.parse(atob(parts[1]));
          if (payload.exp && payload.exp < Date.now() / 1000) {
            localStorage.removeItem('token');
            localStorage.removeItem('refreshToken');
          }
        } catch (e) {
          // Invalid payload, clear token
          localStorage.removeItem('token');
          localStorage.removeItem('refreshToken');
        }
      }
    } catch {
      localStorage.removeItem('token');
      localStorage.removeItem('refreshToken');
    }
  }


  const questionCountValue = questionCount ||
    parseInt(import.meta.env.VITE_QUESTION_GENERATION_COUNT) || 5;

  try {

    // For question generation, don't require auth (endpoint uses AllowAny)
    // Only send token if it's valid, otherwise proceed without it
    const headers = buildHeaders(false);

    const response = await axios.post(
      `${API_BASE_URL}/api/gemini/generate-questions/`,
      {
        job_role: jobRole,
        years_of_experience: yearsOfExperience,
        candidate_name: candidateName,
        question_count: questionCountValue,
        session_id: sessionId,
        focus_areas: focusAreas
      },
      {
        headers,
        timeout: 120000 // 120 seconds timeout to prevent broken pipe
      }
    );

    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    console.error('Error generating questions:', error);

    // Better error messages
    let errorMessage = 'Failed to generate questions';

    if (error.code === 'ECONNREFUSED' || error.message.includes('Network Error') || error.message.includes('ERR_CONNECTION_REFUSED')) {
      errorMessage = 'Cannot connect to backend server. Please make sure the Django server is running on http://localhost:8000';
    } else if (error.response && error.response.status === 429) {
      errorMessage = 'Gemini API Quota Exceeded. Please wait a moment before trying again (Free tier limits reached).';
    } else if (error.response) {
      // Server responded with error status
      if (error.response && error.response.status === 401) {
        // Clear invalid token and retry without token (since endpoint allows unauthenticated access)
        console.log('401 error detected, clearing invalid token and retrying without authentication...');
        localStorage.removeItem('token');
        localStorage.removeItem('refreshToken');

        // Retry the request without token
        try {
          const retryResponse = await axios.post(
            `${API_BASE_URL}/api/gemini/generate-questions/`,
            {
              job_role: jobRole,
              years_of_experience: yearsOfExperience,
              candidate_name: candidateName,
              question_count: questionCountValue,
              session_id: sessionId
            },
            {
              headers: {
                'Content-Type': 'application/json'
                // No Authorization header - endpoint uses AllowAny
              }
            }
          );

          console.log('Retry successful - questions generated without authentication');
          return {
            success: true,
            data: retryResponse.data
          };
        } catch (retryError) {
          console.error('Retry failed:', retryError);
          // If retry also fails, show the original error or retry error
          if (retryError.response) {
            errorMessage = retryError.response.data?.error || retryError.response.data?.detail || `Server error: ${retryError.response.status}`;
          } else {
            errorMessage = retryError.message || 'Failed to generate questions. Please check if the backend server is running.';
          }
        }
      } else {
        errorMessage = error.response?.data?.error || error.response?.data?.detail || `Server error: ${error.response?.status || 'Unknown'}`;
      }
    } else if (error.request) {
      // Request was made but no response received
      errorMessage = 'No response from server. Please check if the backend is running.';
    } else {
      errorMessage = error.message || 'Failed to generate questions';
    }

    return {
      success: false,
      error: errorMessage
    };
  }
};

/**
 * Send a chat message to Gemini
 * @param {Object} params - Chat parameters
 * @param {string} params.message - User message
 * @param {string} [params.sessionId] - Conversation session ID
 * @param {Array} [params.conversationHistory] - Previous conversation history
 * @param {string} [params.systemInstruction] - Optional system instruction
 * @param {number} [params.temperature] - Temperature for generation (0-1)
 * @returns {Promise<Object>} Response with AI reply
 */
export const sendChatMessage = async ({
  message,
  sessionId = null,
  conversationHistory = [],
  systemInstruction = null,
  temperature = 0.7
}) => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/api/gemini/chat/`,
      {
        message,
        session_id: sessionId,
        conversation_history: conversationHistory,
        system_instruction: systemInstruction,
        temperature
      },
      { headers: buildHeaders() }
    );

    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    console.error('Error sending chat message:', error);
    return {
      success: false,
      error: error.response?.data?.error || error.message || 'Failed to send message'
    };
  }
};

/**
 * Get conversation history for a session
 * @param {string} sessionId - Conversation session ID
 * @returns {Promise<Object>} Response with conversation history
 */
export const getConversationHistory = async (sessionId) => {
  try {
    const response = await axios.get(
      `${API_BASE_URL}/api/gemini/conversation/${sessionId}/`,
      { headers: buildHeaders() }
    );

    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    console.error('Error fetching conversation history:', error);
    return {
      success: false,
      error: error.response?.data?.error || error.message || 'Failed to fetch conversation history'
    };
  }
};

/**
 * Get generated questions for a session
 * @param {string} sessionId - Session ID
 * @returns {Promise<Object>} Response with generated questions
 */
export const getGeneratedQuestions = async (sessionId) => {
  try {
    const response = await axios.get(
      `${API_BASE_URL}/api/gemini/questions/${sessionId}/`,
      { headers: buildHeaders() }
    );

    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    console.error('Error fetching generated questions:', error);
    return {
      success: false,
      error: error.response?.data?.error || error.message || 'Failed to fetch questions'
    };
  }
};

/**
 * Save user response to an interview question
 * @param {Object} params - Response parameters
 * @param {string} params.sessionId - Session ID
 * @param {string} params.questionId - Question ID
 * @param {string} params.questionText - Question text
 * @param {string} params.userAnswer - User's answer (from speech-to-text)
 * @param {string} [params.idealAnswer] - Ideal answer (optional)
 * @param {Array} [params.alternativeAnswers] - Alternative answers (optional)
 * @param {boolean} [params.isPrefetch] - Indicates if the response is part of a prefetch operation (optional)
 * @returns {Promise<Object>} Response with saved data
 */
export const saveUserResponse = async ({
  sessionId,
  questionId,
  questionText,
  userAnswer,
  posture = null,
  emotion = null,
  confidence = 0,
  idealAnswer = null,
  alternativeAnswers = [],
  isPrefetch = false
}) => {
  try {
    const headers = buildHeaders(true);
    const response = await axios.post(
      `${API_BASE_URL}/api/gemini/save-response/`,
      {
        session_id: sessionId,
        question_id: questionId,
        question_text: questionText,
        user_answer: userAnswer,
        posture_status: posture,
        dominant_emotion: emotion,
        emotion_confidence: confidence,
        ideal_answer: idealAnswer,
        alternative_answers: alternativeAnswers,
        is_prefetch: isPrefetch
      },
      { headers }
    );

    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    console.error('Error saving user response:', error);

    // Check for 401 Unauthorized (Session Expired)
    if (error.response && error.response.status === 401) {
      console.warn('Session expired (401). Redirecting to login...');
      localStorage.removeItem('token');
      localStorage.removeItem('refreshToken');
      window.location.href = '/login';
      return { success: false, error: 'Session expired. Please log in again.' };
    }

    return {
      success: false,
      error: error.response?.data?.error || error.message || 'Failed to save response'
    };
  }
};

/**
 * Process user response and get follow-up question if needed
 * @param {Object} params - Parameters
 * @param {string} params.questionId - Question ID
 * @param {string} params.question - Question text
 * @param {string} params.userResponse - User's response
 * @param {string} params.jobRole - Job role
 * @param {string} params.yearsOfExperience - Years of experience
 * @param {string} [params.candidateName] - Candidate name
 * @param {string} [params.sessionId] - Session ID
 * @returns {Promise<Object>} Response with follow-up data
 */
export const processUserResponse = async ({
  questionId,
  question,
  userResponse,
  jobRole,
  yearsOfExperience,
  candidateName = null,
  sessionId = null
}) => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/api/gemini/process-response/`,
      {
        question_id: questionId,
        question: question,
        user_response: userResponse,
        job_role: jobRole,
        years_of_experience: yearsOfExperience,
        candidate_name: candidateName,
        session_id: sessionId
      },
      { headers: buildHeaders() }
    );

    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    console.error('Error processing user response:', error);
    return {
      success: false,
      error: error.response?.data?.error || error.message || 'Failed to process response'
    };
  }
};

/**
 * End the interview session
 * @param {string} sessionId - Session ID
 * @returns {Promise<Object>} Response
 */
export const endInterview = async (sessionId) => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/api/gemini/end-interview/`,
      { session_id: sessionId },
      { headers: buildHeaders() }
    );

    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    console.error('Error ending interview:', error);
    return {
      success: false,
      error: error.response?.data?.error || error.message || 'Failed to end interview'
    };
  }
};

