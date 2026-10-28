import { useState, useEffect, useRef, useCallback, Suspense, Component } from 'react'
import { Canvas } from '@react-three/fiber'
import { PerspectiveCamera, Environment, OrbitControls, Stage, Center, Html } from '@react-three/drei'
import { Experience } from './components/Experience.jsx'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import './interview.css'
import Navbar from './nav-bar.jsx';
import { saveUserResponse, endInterview } from './services/geminiService';
import { recordAudioAsWav } from './services/audioUtils';
import Background3D from './components/Background3D';
import { useToast } from './context/ToastContext';

// API Base URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

// Import asset correctly
import avatarImage from './assets/professional_ai_interviewer.png';
// Basic Error Boundary for 3D content
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("3D Render Error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div style={{ padding: 20, textAlign: 'center', color: 'red' }}>
          <h3>Avatar Error</h3>
          <p>{this.state.error?.message}</p>
        </div>
      );
    }
    return this.props.children;
  }
}

function Interview() {
  const { addToast } = useToast();
  const navigate = useNavigate();
  const [postureLabel, setPostureLabel] = useState(null);
  const [faceCount, setFaceCount] = useState(0);
  const [isDetecting, setIsDetecting] = useState(false);
  const [hasSpeech, setHasSpeech] = useState(false);
  const [streamReady, setStreamReady] = useState(false);

  // Emotion detection state
  const [dominantEmotion, setDominantEmotion] = useState('NEUTRAL');
  const [emotionConfidence, setEmotionConfidence] = useState(0);
  const [speakerStatus, setSpeakerStatus] = useState('single');

  const [isInterviewee, setIsInterviewee] = useState(true);
  const [totalQuestionsAsked, setTotalQuestionsAsked] = useState(0);

  // ── Tab-Switch / External-Cheat Detection ────────────────────────────────
  const [tabSwitchCount, setTabSwitchCount] = useState(0);
  const [tabSwitchBannerVisible, setTabSwitchBannerVisible] = useState(false);
  const tabSwitchBannerTimerRef = useRef(null);
  const tabSwitchSessionRef = useRef(null); // keeps session_id in sync for the listeners


  // Interview questions state
  const [questions, setQuestions] = useState([]);
  const [idealAnswers, setIdealAnswers] = useState([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [questionSubtitle, setQuestionSubtitle] = useState('');
  const [userAnswerSubtitle, setUserAnswerSubtitle] = useState('');

  const [isListening, setIsListening] = useState(false);
  const [candidateInfo, setCandidateInfo] = useState(null);
  const [isSpeaking, setIsSpeaking] = useState(false);

  // Interview flow state
  const [interviewStage, setInterviewStage] = useState('initial'); // 'initial', 'greeting', 'listening_for_start', 'question_speaking', 'listening_for_answer', 'processing'

  const currentAnswerRef = useRef('');
  const accumulatedTranscriptRef = useRef(''); // Added for smoother subtitles
  const recognitionRef = useRef(null);
  const synthesisRef = useRef(null);
  const interviewStageRef = useRef('initial');

  const isListeningRef = useRef(false);

  // Custom setter to keep ref in sync
  const setStage = (newStage) => {
    console.log(`[STAGE CHANGE] ${interviewStageRef.current} -> ${newStage}`);
    interviewStageRef.current = newStage;
    setInterviewStage(newStage);
  };

  const setListening = (val) => {
    isListeningRef.current = val;
    setIsListening(val);
  };

  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [micEnabled, setMicEnabled] = useState(false);
  const [error, setError] = useState(null);
  const [mediaInitialized, setMediaInitialized] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [preloadedNextQuestion, setPreloadedNextQuestion] = useState(null);
  const [showSpeakNow, setShowSpeakNow] = useState(false);
  const [questionFeedback, setQuestionFeedback] = useState([]); // NEW: Store feedback for each question
  const [lastQuestionFeedback, setLastQuestionFeedback] = useState(null); // Last question's feedback to show
  const [isProcessing, setIsProcessing] = useState(false);
  const [micLevel, setMicLevel] = useState(0); // Audio level for visualization
  const analyserRef = useRef(null);
  const dataArrayRef = useRef(null);
  const animationFrameRef = useRef(null);

  // Removed static string path in favor of import



  const [backgroundDetectionEnabled] = useState(true);

  // Refs for video elements
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const detectionIntervalRef = useRef(null);
  const canvasRef = useRef(null);

  // Audio processing refs
  const audioIntervalRef = useRef(null);
  const emotionCounterRef = useRef(0);
  const persistentAudioContextRef = useRef(null);

  // Manage body styles for fullscreen interview mode
  useEffect(() => {
    // Save original styles
    const originalStyle = window.getComputedStyle(document.body).overflow;
    const originalBg = document.body.style.backgroundColor;

    // Apply interview styles
    document.body.style.backgroundColor = '#f5f0ff';

    // Cleanup on unmount
    return () => {
      document.body.style.overflow = originalStyle;
      document.body.style.backgroundColor = originalBg;
    };
  }, []);

  // Check authentication on mount - redirect to login if not authenticated
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token || token.trim() === '' || token === 'null' || token === 'undefined') {
      console.log('No token found, redirecting to login');
      navigate('/login');
      return;
    }

    // Validate token format
    try {
      const parts = token.split('.');
      if (parts.length === 3) {
        try {
          const payload = JSON.parse(atob(parts[1]));
          // Check if token is expired
          if (payload.exp && payload.exp < Date.now() / 1000) {
            localStorage.removeItem('token');
            localStorage.removeItem('refreshToken');
            navigate('/login');
            return;
          }
          // Token is valid
          return;
        } catch {
          // Invalid payload
          localStorage.removeItem('token');
          localStorage.removeItem('refreshToken');
        }
      }
    } catch {
      // Invalid format
      localStorage.removeItem('token');
      localStorage.removeItem('refreshToken');
    }

    // Token is invalid
    navigate('/login');
  }, [navigate]);

  const [isActuallySpeaking, setIsActuallySpeaking] = useState(false);
  const isActuallySpeakingRef = useRef(false);

  const setActuallySpeaking = (val) => {
    isActuallySpeakingRef.current = val;
    setIsActuallySpeaking(val);
  };

  // Generate session ID on mount
  useEffect(() => {
    const generateSessionId = () => {
      return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    };

    // Priority: questionSessionId (from choice.jsx) -> currentSessionId -> candidateInfo.sessionId -> new
    const questionSessionId = localStorage.getItem('questionSessionId');
    const storedSessionId = localStorage.getItem('currentSessionId');
    const storedCandidateInfo = localStorage.getItem('candidateInfo');
    const candidateSessionId = storedCandidateInfo ? JSON.parse(storedCandidateInfo).sessionId : null;

    const finalSessionId = questionSessionId || storedSessionId || candidateSessionId || generateSessionId();

    setSessionId(finalSessionId);
    if (!storedSessionId) {
      localStorage.setItem('currentSessionId', finalSessionId);
    }
  }, []);

  const lastSpeechTimeRef = useRef(0);

  useEffect(() => {
    const checkSilence = setInterval(() => {
      if (isListeningRef.current) {
        const now = Date.now();
        if (now - lastSpeechTimeRef.current > 3000) {
          setActuallySpeaking(false);
        }
      }
    }, 1000);
    return () => clearInterval(checkSilence);
  }, []);

  // Load questions from localStorage on mount
  useEffect(() => {
    const loadQuestions = async () => {
      try {
        const storedQuestions = localStorage.getItem('generatedQuestions');
        const storedCandidateInfo = localStorage.getItem('candidateInfo');

        if (storedQuestions) {
          const questionsData = JSON.parse(storedQuestions);

          // Load preloaded next question
          const storedPreloaded = localStorage.getItem('preloadedNextQuestion');
          console.log('Stored preloaded question:', storedPreloaded);
          if (storedPreloaded) {
            try {
              const parsed = JSON.parse(storedPreloaded);
              console.log('Parsed preloaded question:', parsed);
              setPreloadedNextQuestion(parsed);
            } catch (e) {
              console.error('Failed to parse preloaded question:', e);
            }
          }

          // Load ideal answers from localStorage first
          const storedIdealAnswers = localStorage.getItem('idealAnswers');
          if (storedIdealAnswers) {
            try {
              const idealAnswersData = JSON.parse(storedIdealAnswers);
              setIdealAnswers(idealAnswersData);
            } catch (error) {
              console.error('Error parsing ideal answers:', error);
            }
          }

          // Set first question
          if (questionsData.length > 0) {
            const firstQ = questionsData[0];


            // If we converted, use converted, otherwise use original but ensure reference
            const finalQuestions = (questionsData[0].question_id) ? questionsData :
              questionsData.map((q, idx) => ({
                question_id: `q_${idx}_${Date.now()}`,
                question: typeof q === 'string' ? q : q.question || ''
              }));

            setQuestions(finalQuestions);
            setCurrentQuestion(finalQuestions[0]);
          }
        }

        if (storedCandidateInfo) {
          const info = JSON.parse(storedCandidateInfo);
          setCandidateInfo(info);
        }
      } catch (error) {
        console.error('Error loading questions:', error);
      }
    };

    loadQuestions();
  }, []);

  // DISABLED: This was causing redirect loops
  // Redirect to prepare if no questions loaded
  // useEffect(() => {
  //   if (questions.length === 0 && !candidateInfo) {
  //     console.warn('No questions or candidate info found. Redirecting to choice page...');
  //     setTimeout(() => {
  //       navigate('/choice');
  //     }, 2000);
  //   }
  // }, [questions, candidateInfo, navigate]);

  // Initialize Speech Recognition and Synthesis once
  useEffect(() => {
    // Initialize Web Speech API
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = true; // Keep listening until manually stopped
      recognitionRef.current.interimResults = true;
      recognitionRef.current.maxAlternatives = 1;
      recognitionRef.current.lang = 'en-US'; // Reverted to en-US as requested

      // Prevent auto-stopping on silence
      recognitionRef.current.onsoundstart = () => {
        setActuallySpeaking(true);
      };

      recognitionRef.current.onsoundend = () => {
        // Do NOT stop recognition here. Just update UI state.
        setActuallySpeaking(false);
      };

      recognitionRef.current.onspeechstart = () => {
        setActuallySpeaking(true);
      };

      recognitionRef.current.onspeechend = () => {
        setActuallySpeaking(false);
      };

      recognitionRef.current.onresult = (event) => {
        lastSpeechTimeRef.current = Date.now();
        setActuallySpeaking(true);
        let interimTranscript = '';
        let newFinalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            newFinalTranscript += transcript + ' ';
          } else {
            interimTranscript += transcript;
          }
        }

        // Add to our persistent accumulation
        if (newFinalTranscript) {
          accumulatedTranscriptRef.current += newFinalTranscript;
        }

        const displayedTranscript = (accumulatedTranscriptRef.current + interimTranscript).trim();

        currentAnswerRef.current = displayedTranscript;
        setUserAnswerSubtitle(displayedTranscript);
      };

      recognitionRef.current.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        if (event.error === 'no-speech') return;
        // Do not stop listening on error if possible, just log
      };

      recognitionRef.current.onend = () => {
        console.log('Speech recognition ended. Ref isListening:', isListeningRef.current);

        // AGGRESSIVE RESTART: If we are supposed to be listening, RESTART IMMEDIATELY
        if (isListeningRef.current) {
          try {
            console.log('🔄 Restarting Speech Recognition...');
            recognitionRef.current.start();
          } catch (e) {
            console.log('Could not restart recognition immediately:', e);
          }
        }
      };
    }

    // Initialize Speech Synthesis
    if ('speechSynthesis' in window) {
      synthesisRef.current = window.speechSynthesis;
      const loadVoices = () => {
        synthesisRef.current.getVoices();
        console.log('Voices loaded');
      };
      loadVoices();
      if (synthesisRef.current.onvoiceschanged !== undefined) {
        synthesisRef.current.onvoiceschanged = loadVoices;
      }
    }

    // Audio Visualizer Setup
    const setupVisualizer = () => {
      if (streamRef.current && !analyserRef.current) {
        try {
          const audioContext = persistentAudioContextRef.current || new (window.AudioContext || window.webkitAudioContext)();
          if (!persistentAudioContextRef.current) persistentAudioContextRef.current = audioContext;

          const analyser = audioContext.createAnalyser();
          analyser.fftSize = 256;
          const bufferLength = analyser.frequencyBinCount;
          const dataArray = new Uint8Array(bufferLength);

          const source = audioContext.createMediaStreamSource(streamRef.current);
          source.connect(analyser);

          analyserRef.current = analyser;
          dataArrayRef.current = dataArray;

          const updateLevel = () => {
            if (!analyserRef.current) return;
            analyserRef.current.getByteFrequencyData(dataArrayRef.current);
            let sum = 0;
            for (let i = 0; i < dataArrayRef.current.length; i++) {
              sum += dataArrayRef.current[i];
            }
            const average = sum / dataArrayRef.current.length;
            setMicLevel(average);
            animationFrameRef.current = requestAnimationFrame(updateLevel);
          };
          updateLevel();
        } catch (e) {
          console.error('Error setting up visualizer:', e);
        }
      }
    };

    if (mediaInitialized) {
      setupVisualizer();
    }

    return () => {
      if (recognitionRef.current) recognitionRef.current.stop();
      if (synthesisRef.current) synthesisRef.current.cancel();
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      if (persistentAudioContextRef.current) {
        persistentAudioContextRef.current.close();
        persistentAudioContextRef.current = null;
      }
    };
  }, [mediaInitialized]);

  // Recognition is managed explicitly via setListening and startListening
  /*
  useEffect(() => {
    if (!recognitionRef.current) return;
  
    if (isListening) {
      try {
        recognitionRef.current.start();
        console.log('MIC ACTIVE');
      } catch (e) {
        // Recognition might already be started
        console.warn('Recognition start error:', e.message);
      }
    } else {
      try {
        recognitionRef.current.stop();
        console.log('MIC INACTIVE');
      } catch (e) {
        console.warn('Recognition stop error:', e.message);
      }
    }
  }, [isListening]);
  */

  // Function to start listening for user answer
  const startListening = useCallback(() => {
    if (!recognitionRef.current || isListeningRef.current) return;

    try {
      currentAnswerRef.current = '';
      accumulatedTranscriptRef.current = ''; // Clear for new answer
      setUserAnswerSubtitle('');

      // Clear any existing transcripts to prevent "ghost" text
      if (recognitionRef.current.abort) recognitionRef.current.abort();

      setTimeout(() => {
        if (recognitionRef.current) {
          recognitionRef.current.start();
          setListening(true);
        }
      }, 50);

      // TRIGGER BACKGROUND PRE-LOADING OF NEXT QUESTION
      if (!preloadedNextQuestion && currentQuestion && interviewStageRef.current === 'listening_for_answer') {
        console.log('Background pre-loading next question...');
      }
    } catch (error) {
      console.error('Error starting speech recognition:', error);
    }
  }, [preloadedNextQuestion, currentQuestion]);

  // Function to speak question using TTS with female voice
  const speakQuestion = useCallback((questionText) => {
    if (!questionText) return;

    // Dispatch event to the Avatar component
    window.dispatchEvent(new CustomEvent("speak-text", { detail: { text: questionText } }));

    // Listen for avatar speaking states to sync UI
    const startSpeaking = () => setIsSpeaking(true);
    const stopSpeaking = () => {
      setIsSpeaking(false);
      window.removeEventListener("avatar-speaking-start", startSpeaking);
      window.removeEventListener("avatar-speaking-end", stopSpeaking);

      // SHOW "SPEAK NOW" FOR 1 SECOND
      setShowSpeakNow(true);
      setTimeout(() => setShowSpeakNow(false), 1000);

      // Transition logic
      const currentStage = interviewStageRef.current;
      if (currentStage === 'greeting' || currentStage === 'initial' || currentStage === 'question_speaking') {
        const isActuallyGreeting = currentQuestion?.question_id === 'GREETING' || currentQuestion?.type === 'greeting';

        if ((currentStage === 'greeting' || currentStage === 'initial') && isActuallyGreeting) {
          if (questions && questions.length > 1) {
            const q1 = questions[1];
            setCurrentQuestion(q1);
            setQuestionSubtitle(q1.question);
            setStage('question_speaking');
            setTimeout(() => speakQuestion(q1.question), 50);
          }
        } else {
          const isClosing = currentQuestion?.question_id === 'CLOSING' || currentQuestion?.type === 'closing';
          if (isClosing) {
            setStage('completed');
            setTimeout(() => {
              navigate('/feedback', { state: { sessionId, questionFeedback } });
            }, 5000);
            return;
          }

          setStage('listening_for_answer');
          setTimeout(() => startListening(), 50);
        }
      }
    };

    window.addEventListener("avatar-speaking-start", startSpeaking);
    window.addEventListener("avatar-speaking-end", stopSpeaking);

  }, [interviewStage, startListening, currentQuestion, questions, sessionId, questionFeedback, navigate]);

  // TRIGGER BACKGROUND PRE-LOADING OF NEXT QUESTION
  useEffect(() => {
    if (interviewStage === 'listening_for_answer' && !preloadedNextQuestion && currentQuestion && sessionId) {
      const triggerPrefetch = async () => {
        // PREFETCH DISABLED TEMPORARILY - CAUSING HISTORY SPAM
        /*
        try {
          console.log('Proactively pre-fetching next question in background...');
          // Using a special flag so backend knows it's a prefetch
          // and doesn't finalize the answer yet, but returns a potential next question
          const result = await saveUserResponse({
            sessionId: sessionId,
            questionId: currentQuestion.question_id,
            questionText: currentQuestion.question,
            userAnswer: "PREFETCHING",
            isPrefetch: true
          });
  
          if (result.success && result.data && result.data.next_question) {
            console.log('Background pre-fetch succeeded:', result.data.next_question.question_id);
            setPreloadedNextQuestion(result.data.next_question);
          }
        } catch (e) {
          console.warn('Background pre-fetch failed or not supported:', e.message);
        }
        */
      };

      const timer = setTimeout(triggerPrefetch, 2000); // Start pre-fetching 2s into their answer
      return () => clearTimeout(timer);
    }
  }, [interviewStage, preloadedNextQuestion, sessionId, currentQuestion]);



  const formatStructuredSpeech = (text) => {
    if (!text) return "";
    let formatted = text;

    // Convert "first one is", "second one is", "firstly", "secondly" to bullet points
    const bulletKeywords = [
      { regex: /firstly|first one is|first point is/gi, bullet: "\n• First Point: " },
      { regex: /secondly|second one is|second point is/gi, bullet: "\n• Second Point: " },
      { regex: /thirdly|third one is|third point is/gi, bullet: "\n• Third Point: " },
      { regex: /finally|lastly|last point is/gi, bullet: "\n• Final Point: " }
    ];

    bulletKeywords.forEach(item => {
      formatted = formatted.replace(item.regex, item.bullet);
    });

    // Handle "which involves" as an explanation connector
    formatted = formatted.replace(/which involves/gi, "\n  ↳ (Explanation): which involves");

    return formatted.trim();
  };

  const handleEndInterview = useCallback(async (force = false) => {
    if (force || window.confirm('Are you sure you want to end the interview? Progress will be saved.')) {
      try {
        await endInterview(sessionId);
        navigate('/feedback', { state: { sessionId, questionFeedback } });
      } catch (error) {
        console.error('Error ending interview:', error);
        navigate('/feedback', { state: { sessionId, questionFeedback } });
      }
    }
  }, [sessionId, questionFeedback, navigate]);

  // Function to move to next question (called after feedback)
  const handleNextQuestion = useCallback(() => {
    setLastQuestionFeedback(null);

    const currentIdx = questions.findIndex(q => q.question_id === currentQuestion.question_id);
    const nextIdx = currentIdx + 1;

    // Auto-end if we have asked 5 questions (or more)
    if (nextIdx >= 5) {
      setStage('completed');
      handleEndInterview(true);
      return;
    }

    let nextQ = null;

    if (nextIdx < questions.length) {
      nextQ = questions[nextIdx];
    }

    if (nextQ) {
      if (nextQ.question_id === 'CLOSING' || nextQ.type === 'closing') {
        setStage('completed');
        setQuestionSubtitle(nextQ.question);
        speakQuestion(nextQ.question);
        setTimeout(() => {
          handleEndInterview(true);
        }, 8000);
      } else {
        setCurrentQuestion(nextQ);
        setCurrentQuestionIndex(nextIdx);
        setQuestionSubtitle(nextQ.question || '');
        setUserAnswerSubtitle('');
        setStage('question_speaking');
        setTimeout(() => speakQuestion(nextQ.question), 250);
      }
    } else {
      setStage('completed');
      handleEndInterview(true);
    }
  }, [currentQuestion, questions, sessionId, questionFeedback, navigate, speakQuestion, handleEndInterview]);

  // Function to stop listening and save answer
  const stopListeningAndSave = useCallback(async () => {
    if (!recognitionRef.current || !isListeningRef.current) return;

    // 1. STOP Recognition
    recognitionRef.current.stop();
    setListening(false);
    setIsProcessing(true);
    setStage('processing');

    // 2. Capture user answer and current question context
    // 2. Capture and format user answer
    const rawAnswer = currentAnswerRef.current.trim();

    // AUTOMATIC REFINEMENT (Quillbot-style)
    let refinedAnswer = rawAnswer;
    if (rawAnswer.length > 5) {
      try {
        setUserAnswerSubtitle("✨ Enhancing your answer..."); // Visual feedback
        const refineResponse = await axios.post(`${API_BASE_URL}/api/gemini/refine-transcript/`, {
          text: rawAnswer
        });
        if (refineResponse.data && refineResponse.data.refined_text) {
          refinedAnswer = refineResponse.data.refined_text;
          console.log("Auto-Refined:", refinedAnswer);
          setUserAnswerSubtitle(refinedAnswer); // Show refined version briefly
          addToast({ title: 'Enhanced', description: 'AI has refined your speech for clarity.' }, 'info', 2000);
        }
      } catch (refineErr) {
        console.error("Auto-refinement failed, using raw:", refineErr);
      }
    }

    const userAnswer = formatStructuredSpeech(refinedAnswer);
    const qToSave = currentQuestion;

    if (!userAnswer || !qToSave) {
      setIsProcessing(false);
      setStage('listening_for_answer');
      return;
    }

    const idealAnswerData = idealAnswers.find(
      ans => ans.question_id === qToSave.question_id
    );

    try {
      // 3. SAVE and Wait for Feedback
      const result = await saveUserResponse({
        sessionId,
        questionId: qToSave.question_id,
        questionText: qToSave.question,
        userAnswer, // Uses the refined Answer
        posture: postureLabel,
        emotion: dominantEmotion,
        confidence: emotionConfidence,
        idealAnswer: idealAnswerData?.ideal_answer || null,
        alternativeAnswers: idealAnswerData?.alternative_answers || []
      });

      if (result.success) {
        setTotalQuestionsAsked(prev => prev + 1);

        if (result.feedback) {
          const feedbackItem = {
            ...result.feedback,
            question: qToSave.question,
            user_answer: userAnswer
          };
          setQuestionFeedback(prev => [...prev, feedbackItem]);
        }

        // Always proceed to next question (no intermediate feedback)
        setIsProcessing(false);
        addToast({ title: 'Answer Saved', description: 'Your response has been recorded.' }, 'success', 2000);
        handleNextQuestion();
      } else {
        // Save failed, still proceed
        setIsProcessing(false);
        addToast({ title: 'Saved with Warning', description: 'Response saved locally but sync failed.' }, 'warning', 3000);
        handleNextQuestion();
      }
    } catch (error) {
      console.error('Error in save flow:', error);
      setIsProcessing(false);
      addToast({ title: 'Error Saving', description: 'Could not save your response. Proceeding...' }, 'error', 3000);
      handleNextQuestion();
    }

  }, [isListening, currentQuestion, questions, idealAnswers, sessionId, handleNextQuestion, postureLabel, dominantEmotion, emotionConfidence, addToast]);


  // handleEndInterview moved up

  // Handle Greeting and Start Logic
  useEffect(() => {
    // Stage 1: Initial Greeting from Backend
    if (mediaInitialized && questions.length > 0 && interviewStage === 'initial') {
      const greetingQ = questions[0];

      setStage('greeting');
      setCurrentQuestion(greetingQ);
      setQuestionSubtitle(greetingQ.question);

      // Speak the greeting from backend
      setTimeout(() => {
        speakQuestion(greetingQ.question);
      }, 1500);
    }
  }, [mediaInitialized, questions, candidateInfo, speakQuestion, interviewStage]);

  // Keyword detection removed for auto-start

  // Auto-speak question only if NOT initial (handled by logic above)
  /*
  useEffect(() => {
    if (currentQuestion && currentQuestion.question && interviewStage === 'question_speaking') {
      // Small delay before speaking
      const timer = setTimeout(() => {
        speakQuestion(currentQuestion.question);
      }, 500);
   
      return () => clearTimeout(timer);
    }
  }, [currentQuestion, speakQuestion, interviewStage]);
  */

  // Function to capture frame from video and convert to base64
  const captureFrame = () => {
    if (!videoRef.current || !videoRef.current.videoWidth) {
      return null;
    }

    // Create canvas if it doesn't exist
    if (!canvasRef.current) {
      canvasRef.current = document.createElement('canvas');
    }
    const canvas = canvasRef.current;
    const video = videoRef.current;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Convert to base64
    return canvas.toDataURL('image/jpeg', 0.8);
  };

  // Function to capture audio chunk using AudioContext (for speaker detection - shorter)
  const captureAudioChunk = useCallback(async () => {
    if (!streamRef.current || !micEnabled) {
      return null;
    }

    try {
      // Ensure we have a persistent AudioContext
      if (!persistentAudioContextRef.current) {
        persistentAudioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      }

      // Record for 1.5 seconds using the persistent context (good for both speaker & emotion)
      return await recordAudioAsWav(streamRef.current, 1500, persistentAudioContextRef.current);
    } catch (err) {
      console.error('Error capturing audio:', err);
      return null;
    }
  }, [micEnabled]);

  // Function to save user response to backend


  // Consolidated function to send audio chunk for both speaker and emotion detection
  const sendAudioBoth = useCallback(async (audioBase64) => {
    if (!audioBase64 || !micEnabled) return;

    // GATED: Don't detect during final processing
    if (isProcessing) {
      setDominantEmotion('CALIBRATING...');
      return;
    }

    try {
      const response = await axios.post(`${API_BASE_URL}/api/detections/both_audio/`, {
        audio: audioBase64,
        session_id: sessionId,
        sampling_rate: 16000
      }, {
        headers: { 'Content-Type': 'application/json' }
      });

      if (response.data.success) {
        const { speaker, emotion } = response.data;

        // Update Speaker State
        setHasSpeech(speaker.has_speech);
        setSpeakerStatus(speaker.is_multiple_speakers ? 'multiple' : 'single');
        if (speaker.is_interviewee !== undefined) {
          setIsInterviewee(speaker.is_interviewee);
        }

        // Update Emotion State
        if (emotion.dominant_emotion && emotion.dominant_emotion !== 'neutral') {
          // If the model detected something specific, always update
          setDominantEmotion(emotion.dominant_emotion);
          setEmotionConfidence(emotion.confidence || 0);
        } else if (emotion.has_speech && emotion.confidence > 0) {
          // It is neutral, but we have a valid confidence
          setDominantEmotion('neutral');
          setEmotionConfidence(emotion.confidence);
        }
      }
    } catch (err) {
      console.error('Merged audio detection error:', err);
    }
  }, [micEnabled, sessionId, isProcessing]);

  // Function to send frame to backend for detection
  const sendFrameForDetection = useCallback(async () => {
    // Run detection when camera is enabled and not already detecting
    if (!cameraEnabled || isDetecting) {
      return;
    }

    try {
      setIsDetecting(true);
      console.log('Sending frame for detection...');
      const imageBase64 = captureFrame();

      if (!imageBase64) {
        setIsDetecting(false);
        return;
      }

      // Send to backend API
      const response = await axios.post(`${API_BASE_URL}/api/detections/both/`, {
        image: imageBase64,
        session_id: sessionId
      }, {
        headers: {
          'Content-Type': 'application/json',
        }
      });

      // Update state with results
      if (response.data.success) {
        console.log('Detection results:', response.data);
        if (response.data.posture && response.data.posture.posture_label) {
          setPostureLabel(response.data.posture.posture_label);
          console.log('Posture detected:', response.data.posture.posture_label);
        } else {
          // Clear posture if not detected
          setPostureLabel(null);
        }
        if (response.data.faces !== undefined) {
          const faceCountValue = response.data.faces.face_count || 0;
          setFaceCount(faceCountValue);
          console.log('Face count:', faceCountValue);
        }
      }
    } catch (err) {
      console.error('Detection error:', err);
      console.error('Error details:', err.response?.data || err.message);
      // Don't show error to user for every failed detection, just log it
    } finally {
      setIsDetecting(false);
    }
  }, [cameraEnabled, isDetecting, sessionId]);

  // Consolidate mount effects
  const initializeMedia = useCallback(async () => {
    try {
      console.log('Requesting media access...');

      // Request microphone access first (for interviewee)
      let audioStream = null;
      try {
        audioStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
            sampleRate: 16000
          }
        });
        console.log('Microphone access granted');
      } catch (audioErr) {
        console.error('Microphone access error:', audioErr);
        setError(`Microphone access error: ${audioErr.message}. Please allow microphone access to continue the interview.`);
        return;
      }

      // Request camera access
      let videoStream = null;
      try {
        videoStream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 1280 },
            height: { ideal: 720 },
            facingMode: 'user'
          }
        });
        console.log('Camera access granted');
      } catch (videoErr) {
        console.warn('Camera access error:', videoErr);
        // Continue without camera if user denies
      }

      // Combine streams
      const tracks = [];
      if (audioStream) {
        tracks.push(...audioStream.getAudioTracks());
      }
      if (videoStream) {
        tracks.push(...videoStream.getVideoTracks());
      }

      const combinedStream = new MediaStream(tracks);
      streamRef.current = combinedStream;

      // Set states based on available tracks
      const hasAudio = audioStream !== null && audioStream.getAudioTracks().length > 0;
      const hasVideo = videoStream !== null && videoStream.getVideoTracks().length > 0;

      setMicEnabled(hasAudio);
      setCameraEnabled(hasVideo);
      setMediaInitialized(true);
      setError(null);
      addToast({ title: 'System Ready', description: 'Camera and Microphone connected successfully.' }, 'success', 3000);

      // CRITICAL: Attach stream to video element
      if (videoRef.current) {
        videoRef.current.srcObject = combinedStream;
      }

      // Log track states
      console.log('Video tracks:', combinedStream.getVideoTracks());
      console.log('Audio tracks:', combinedStream.getAudioTracks());
      console.log('Microphone enabled:', hasAudio);
      console.log('Camera enabled:', hasVideo);

    } catch (err) {
      console.error('Error accessing media devices:', err);
      setError(`Media access error: ${err.message}. Please allow camera and microphone access.`);
      setMediaInitialized(false);
    }
  }, [addToast]);

  useEffect(() => {
    initializeMedia();
  }, [initializeMedia]);

  // Effect to attach stream to video element when both are available
  useEffect(() => {
    if (videoRef.current && streamRef.current && mediaInitialized) {
      console.log('Attaching stream to video element...');
      videoRef.current.srcObject = streamRef.current;

      videoRef.current.onloadedmetadata = () => {
        setStreamReady(true);
      };

      videoRef.current.oncanplay = () => {
        videoRef.current.play().catch(console.error);
      };

      videoRef.current.play().catch(console.error);
    }
  }, [mediaInitialized]);

  // Effect to start/stop continuous detection based on camera status
  useEffect(() => {
    // Start detection when camera is enabled and media is initialized
    if (cameraEnabled && mediaInitialized) {
      console.log('Starting continuous face and posture detection...');

      // Clear any existing interval
      if (detectionIntervalRef.current) {
        clearInterval(detectionIntervalRef.current);
      }

      // Start detection interval (every 5 seconds)
      detectionIntervalRef.current = setInterval(() => {
        if (cameraEnabled) {
          sendFrameForDetection();
        }
      }, 5000);

      // Also run detection immediately
      setTimeout(() => {
        if (cameraEnabled) {
          sendFrameForDetection();
        }
      }, 500);

      return () => {
        if (detectionIntervalRef.current) {
          console.log('Stopping continuous detection...');
          clearInterval(detectionIntervalRef.current);
          detectionIntervalRef.current = null;
        }
      };
    } else {
      if (detectionIntervalRef.current) {
        clearInterval(detectionIntervalRef.current);
        detectionIntervalRef.current = null;
      }
    }
  }, [cameraEnabled, mediaInitialized]);

  // Effect to start/stop continuous audio detection based on mic status
  useEffect(() => {
    // Start audio detection when mic is enabled and media is initialized
    if (micEnabled && mediaInitialized && backgroundDetectionEnabled) {
      console.log('Starting continuous audio detection...');
      console.log('Starting background audio detection interval');

      // Clear any existing interval
      if (audioIntervalRef.current) {
        clearInterval(audioIntervalRef.current);
      }

      // Reset emotion counter
      emotionCounterRef.current = 0;

      audioIntervalRef.current = setInterval(async () => {
        // GATED: Only detect emotion/speaker when Gemini is listening for an answer
        if (!micEnabled || interviewStageRef.current !== 'listening_for_answer') {
          return;
        }

        try {
          // Capture audio chunk for speaker and emotion detection simultaneously
          const audioBase64 = await captureAudioChunk();
          if (audioBase64) {
            sendAudioBoth(audioBase64);
          }
        } catch (error) {
          console.error('Error in audio detection interval:', error);
        }
      }, 2500); // Reduced frequency (2.5s) to prevent server saturation

      // Cleanup function
      return () => {
        if (audioIntervalRef.current) {
          console.log('Stopping continuous audio detection...');
          clearInterval(audioIntervalRef.current);
          audioIntervalRef.current = null;
        }
        // Reset emotion counter when mic is disabled
        emotionCounterRef.current = 0;
      };
    }
  }, [micEnabled, mediaInitialized, captureAudioChunk, sendAudioBoth, backgroundDetectionEnabled]);

  console.log('Current state:', {
    mediaInitialized,
    cameraEnabled,
    micEnabled,
    streamReady,
    dominantEmotion,
    emotionConfidence
  });

  // Debug effect to log emotion state changes
  useEffect(() => {
    if (dominantEmotion) {
      console.log('✅ Emotion state updated - Displaying:', dominantEmotion, 'Confidence:', emotionConfidence);
    } else {
      console.log('❌ No emotion detected or cleared');
    }
  }, [dominantEmotion, emotionConfidence]);
  // ── Tab-Switch Hook ────────────────────────────────────────────────────────
  // Uses TWO complementary signals for maximum reliability:
  //   1. Page Visibility API (visibilitychange) – fires when the tab is hidden
  //      (e.g. user switches tabs, minimises the window, or the OS locks screen)
  //   2. window blur – fires when ANY OTHER window / application gains focus
  //      (e.g. Alt-Tab, opening a browser Dev-Tools window, screen sharing app)
  useEffect(() => {
    if (!mediaInitialized) return; // Don't attach until session is live

    // Keep the ref in sync so the closure always has the latest sessionId
    tabSwitchSessionRef.current = sessionId;

    const logEvent = async (eventType) => {
      const sid = tabSwitchSessionRef.current;
      if (!sid) return;

      const isSuspicious = eventType === 'tab_hidden' || eventType === 'window_blur';

      if (isSuspicious) {
        setTabSwitchCount(prev => prev + 1);
        setTabSwitchBannerVisible(true);

        // Auto-hide the banner after 6 seconds
        if (tabSwitchBannerTimerRef.current) clearTimeout(tabSwitchBannerTimerRef.current);
        tabSwitchBannerTimerRef.current = setTimeout(() => {
          setTabSwitchBannerVisible(false);
        }, 6000);

        // Briefly pause mic so answer capture is not corrupted
        if (isListeningRef.current && recognitionRef.current) {
          try { recognitionRef.current.stop(); } catch (_) {}
          setListening(false);
          // Resume mic after 1.5s so user can continue answering
          setTimeout(() => {
            if (interviewStageRef.current === 'listening_for_answer') {
              try { recognitionRef.current?.start(); setListening(true); } catch (_) {}
            }
          }, 1500);
        }
      }

      // Post to backend – fire-and-forget, never block the UI
      try {
        axios.post(`${API_BASE_URL}/api/detections/tab-switch/`, {
          session_id: sid,
          event_type: eventType,
          question_id: interviewStageRef.current === 'listening_for_answer'
            ? (currentQuestion?.question_id || '')
            : ''
        }).catch(() => {});
      } catch (_) {}
    };

    // ── Signal 1: Page Visibility API ─────────────────────────────────────
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        logEvent('tab_hidden');
      } else if (document.visibilityState === 'visible') {
        logEvent('tab_restored');
      }
    };

    // ── Signal 2: Window blur (catches Alt-Tab, other-app focus) ──────────
    // Small debounce (200 ms) to avoid false-positives from in-page iframes.
    let blurTimer = null;
    const handleBlur = () => {
      blurTimer = setTimeout(() => {
        // Only flag if the tab is still 'visible' (real external blur, not tab hide)
        if (document.visibilityState === 'visible') {
          logEvent('window_blur');
        }
      }, 200);
    };
    const handleFocus = () => {
      clearTimeout(blurTimer);
      logEvent('window_focus');
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('blur', handleBlur);
    window.addEventListener('focus', handleFocus);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('blur', handleBlur);
      window.removeEventListener('focus', handleFocus);
      if (tabSwitchBannerTimerRef.current) clearTimeout(tabSwitchBannerTimerRef.current);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mediaInitialized, sessionId]);

  return (
    <>
      <Background3D />
      <Navbar minimal={true} />

      <div className="interview-container">
        {/* ── TAB-SWITCH CHEAT ALERT BANNER ─────────────────────────────── */}
        {tabSwitchBannerVisible && (
          <div className="tab-switch-alert-overlay">
            <div className="tab-switch-alert-card">
              <div className="tab-switch-alert-icon">⚠️</div>
              <div className="tab-switch-alert-content">
                <div className="tab-switch-alert-title">EXTERNAL CHEATING DETECTED</div>
                <div className="tab-switch-alert-sub">
                  You left or minimised the interview tab. This has been flagged and recorded.
                  <span className="tab-switch-alert-count"> Incident #{tabSwitchCount}</span>
                </div>
              </div>
              <button
                className="tab-switch-alert-close"
                onClick={() => setTabSwitchBannerVisible(false)}
                aria-label="Dismiss alert"
              >✕</button>
            </div>
          </div>
        )}

        {/* Status Area */}
        <div className="status-bars-container">
          <div className="breadcrumb-bar">
            <div className="breadcrumb-content">
              <span className="live-indicator"><span className="live-dot"></span> Live Interview Session</span>
              <span className="session-badge">Behavioral Interview</span>
            </div>
            <div className="breadcrumb-meta">
              Question {Math.min(totalQuestionsAsked + 1, 5)} of 5
            </div>
          </div>

          <div className="diagnostic-bar">
            <div className="diag-item">
              Posture: <span className={`diag-pill ${(postureLabel && postureLabel.toLowerCase() === 'appropriate') ? 'green' : (postureLabel) ? 'red' : 'red'}`}>
                {postureLabel ? (postureLabel.toLowerCase() === 'appropriate' ? 'APPROPRIATE ✓' : postureLabel.toUpperCase()) : 'NONE'}
              </span>
            </div>
            <div className="diag-item">
              Face Detection: <span className={`diag-pill ${faceCount === 1 ? 'green' : 'red'}`}>
                {faceCount === 1 ? 'SINGLE FACE \u2713' : faceCount > 1 ? 'MULTIPLE' : 'NONE'}
              </span>
            </div>
            <div className="diag-item">
              Multiple Speakers: <span className={`diag-pill ${speakerStatus === 'single' ? 'green' : 'red'}`}>
                {speakerStatus === 'multiple' ? 'MULTIPLE VOICES' : 'SINGLE VOICE \u2713'}
              </span>
            </div>
            <div className="diag-item">
              Identified Speaker: <span className={`diag-pill ${isInterviewee ? 'green' : 'red'}`}>
                {isInterviewee ? 'INTERVIEWEE \u2713' : 'UNIDENTIFIED'}
              </span>
            </div>
            <div className="diag-item">
              Emotion: <span className={`diag-pill ${hasSpeech ? 'grey' : 'light-grey'}`}>
                {hasSpeech ? (dominantEmotion || 'NEUTRAL').toUpperCase() : 'SILENCED'} ({hasSpeech ? `${(emotionConfidence * 100).toFixed(0)}%` : '---'})
              </span>
            </div>
            <div className="diag-item">
              Tab Switches: <span className={`diag-pill ${tabSwitchCount === 0 ? 'green' : tabSwitchCount <= 2 ? 'orange' : 'red'}`}>
                {tabSwitchCount === 0 ? 'NONE ✓' : `${tabSwitchCount} ⚠️`}
              </span>
            </div>
          </div>
        </div>


        {/* Feedback Overlay when question is answered */}
        {interviewStage === 'showing_feedback' && lastQuestionFeedback && (
          <div className="feedback-overlay" style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.85)',
            zIndex: 2000,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            padding: '20px'
          }}>
            <div className="feedback-card" style={{
              background: 'rgba(30,30,40,0.95)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '24px',
              width: '100%',
              maxWidth: '800px',
              maxHeight: '90vh',
              overflowY: 'auto',
              padding: '30px',
              position: 'relative',
              animation: 'fadeInUp 0.4s ease-out',
              color: 'white'
            }}>
              <h2 style={{ color: '#6c5ce7', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                <i className="fa fa-commenting"></i> Question Feedback
              </h2>
              <div style={{ background: '#f8f9fa', padding: '15px', borderRadius: '12px', marginBottom: '20px' }}>
                <p style={{ fontWeight: 700, margin: '0 0 5px 0' }}>Q: {lastQuestionFeedback.question}</p>
                <p style={{ fontStyle: 'italic', margin: 0 }}>Your Answer: "{lastQuestionFeedback.user_answer}"</p>
              </div>

              <div className="feedback-metrics-row" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '15px', marginBottom: '20px' }}>
                <div style={{ background: '#e8f5e9', padding: '12px', borderRadius: '12px', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.7rem', color: '#666' }}>Accuracy Score</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#2ecc71' }}>{Math.round(lastQuestionFeedback.score || (lastQuestionFeedback.metrics?.semantic_score * 100) || 0)}/100</div>
                </div>
                <div style={{ background: '#fff9db', padding: '12px', borderRadius: '12px', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.7rem', color: '#666' }}>Emotion</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 700 }}>{lastQuestionFeedback.metrics?.emotion || 'Neutral'}</div>
                </div>
                <div style={{ background: '#f3f0ff', padding: '12px', borderRadius: '12px', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.7rem', color: '#666' }}>Posture</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 700 }}>{lastQuestionFeedback.metrics?.posture || 'Safe'}</div>
                </div>
              </div>

              <div className="pros-cons-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '30px' }}>
                <div style={{ background: '#f0fff4', padding: '20px', borderRadius: '16px' }}>
                  <h4 style={{ color: '#27ae60', margin: '0 0 10px 0' }}><i className="fa fa-check-circle"></i> Strengths</h4>
                  <ul style={{ paddingLeft: '20px', margin: 0, fontSize: '0.9rem' }}>
                    {(lastQuestionFeedback.positives || ["Great technical content."]).map((p, i) => <li key={i}>{p}</li>)}
                  </ul>
                </div>
                <div style={{ background: '#fff5f5', padding: '20px', borderRadius: '16px' }}>
                  <h4 style={{ color: '#e74c3c', margin: '0 0 10px 0' }}><i className="fa fa-lightbulb-o"></i> Improvement</h4>
                  <ul style={{ paddingLeft: '20px', margin: 0, fontSize: '0.9rem' }}>
                    {(lastQuestionFeedback.negatives || ["Try to be more specific."]).map((n, i) => <li key={i}>{n}</li>)}
                  </ul>
                </div>
              </div>

              <button
                onClick={handleNextQuestion}
                style={{
                  width: '100%',
                  background: '#6c5ce7',
                  color: 'white',
                  border: 'none',
                  padding: '16px',
                  borderRadius: '12px',
                  fontWeight: 800,
                  fontSize: '1rem',
                  cursor: 'pointer',
                  boxShadow: '0 4px 15px rgba(108, 92, 231, 0.3)'
                }}
              >
                Continue to Next Question <i className="fa fa-arrow-right"></i>
              </button>
            </div>
          </div>
        )}

        {/* Dashboard Grid */}
        <div className="dashboard-grid">
          {/* AI Column */}
          <div className="panel-card ai-column">
            <div className="panel-header">
              <i className="fa fa-user-circle"></i> AI Interviewer
              <div style={{ marginLeft: 'auto', fontSize: '0.75rem', color: '#00b894' }}>
                • Online <span style={{ color: '#636e72', marginLeft: '5px' }}>{isSpeaking ? 'Speaking' : 'Listening'}</span>
              </div>
            </div>

            <div className="video-wrapper">
              <div className="avatar-realistic-centered">
                <div style={{
                  width: '100%',
                  height: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  overflow: 'hidden'
                }}>
                  <ErrorBoundary fallback={
                    <img
                      src={avatarImage}
                      alt="AI Interviewer"
                      className="static-avatar-image"
                      style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                        objectPosition: 'top center'
                      }}
                    />
                  }>
                    {/* Zoomed in camera for "Passport Photo" look - Head & Shoulders */}
                    <Canvas shadows camera={{ position: [0, 0.15, 2.2], fov: 10 }}>
                      <Suspense fallback={
                        <Html center>
                          <div style={{ color: 'white', background: 'rgba(0,0,0,0.5)', padding: '10px 20px', borderRadius: '20px', whiteSpace: 'nowrap' }}>
                            <i className="fa fa-spinner fa-spin" style={{ marginRight: '10px' }}></i>
                            Loading AI Interviewer...
                          </div>
                        </Html>
                      }>
                        <Experience />
                      </Suspense>
                    </Canvas>
                  </ErrorBoundary>
                </div>

                <div className={`avatar-pulse ${isSpeaking ? 'active' : ''}`} style={{
                  position: 'absolute',
                  bottom: '20px',
                  right: '20px',
                  width: '12px',
                  height: '12px',
                  borderRadius: '50%',
                  background: isSpeaking ? '#2ecc71' : '#95a5a6',
                  boxShadow: isSpeaking ? '0 0 10px #2ecc71' : 'none',
                  zIndex: 2
                }}></div>
              </div>
            </div>

            {/* NEW: AI Subtitle box below the photo */}
            <div className="ai-subtitle-container" style={{
              padding: '16px 20px',
              minHeight: '80px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderTop: '1px solid rgba(255,255,255,0.5)'
            }}>
              {questionSubtitle ? (
                <div style={{
                  background: 'rgba(255, 255, 255, 0.9)',
                  padding: '12px 20px',
                  borderRadius: '12px',
                  textAlign: 'left',
                  fontWeight: '600',
                  color: '#1e293b',
                  fontSize: '0.95rem',
                  lineHeight: '1.5',
                  backdropFilter: 'blur(12px)',
                  boxShadow: '0 4px 15px rgba(0,0,0,0.1)',
                  width: '100%',
                  border: '1px solid rgba(255,255,255,0.8)'
                }}>
                  {questionSubtitle}
                </div>
              ) : (
                <span style={{ color: '#64748b', fontSize: '0.85rem', fontStyle: 'italic' }}>Waiting for AI to speak...</span>
              )}
            </div>

          </div>

          {/* User Column */}
          <div className="panel-card user-column">
            <div className="panel-header">
              <i className="fa fa-user"></i> You <span style={{ color: '#64748b', fontSize: '0.85rem', marginLeft: '8px' }}>Your Response</span>
            </div>

            <div className="video-wrapper">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="video-element"
              />

              {/* TOP-LEFT: POSTURE PILL */}
              <div style={{ position: 'absolute', top: '12px', left: '12px', zIndex: 10 }}>
                {postureLabel && (
                  <div style={{
                    backgroundColor: (postureLabel.toLowerCase().includes('good') || postureLabel.toLowerCase() === 'appropriate') ? '#f0fdf4' :
                      (postureLabel.toLowerCase().includes('lean') || postureLabel.toLowerCase() === 'defensive') ? '#fefce8' : '#f1f5f9', // Neutral gray for others instead of red
                    color: (postureLabel.toLowerCase().includes('good') || postureLabel.toLowerCase() === 'appropriate') ? '#16a34a' :
                      (postureLabel.toLowerCase().includes('lean') || postureLabel.toLowerCase() === 'defensive') ? '#eab308' : '#64748b',
                    border: '1px solid',
                    borderColor: (postureLabel.toLowerCase().includes('good') || postureLabel.toLowerCase() === 'appropriate') ? '#bbf7d0' :
                      (postureLabel.toLowerCase().includes('lean') || postureLabel.toLowerCase() === 'defensive') ? '#fef08a' : '#cbd5e1',
                    padding: '6px 14px',
                    borderRadius: '6px',
                    fontSize: '0.7rem',
                    fontWeight: '700',
                    textTransform: 'uppercase',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                    backdropFilter: 'blur(4px)'
                  }}>
                    <span style={{ fontSize: '10px' }}>
                      {(postureLabel.toLowerCase().includes('good') || postureLabel.toLowerCase() === 'appropriate') ? '✓' : 'ℹ️'}
                    </span>
                    POSTURE: {postureLabel}
                  </div>
                )}
              </div>

              {/* TOP-RIGHT: FACE DETECTION PILL */}
              <div style={{ position: 'absolute', top: '12px', right: '12px', zIndex: 10 }}>
                <div style={{
                  backgroundColor: faceCount > 1 ? '#fef2f2' : '#f0fdf4',
                  color: faceCount > 1 ? '#dc2626' : '#16a34a',
                  border: '1px solid',
                  borderColor: faceCount > 1 ? '#fecaca' : '#bbf7d0',
                  padding: '6px 14px',
                  borderRadius: '6px',
                  fontSize: '0.7rem',
                  fontWeight: '700',
                  textTransform: 'uppercase',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                  backdropFilter: 'blur(4px)'
                }}>
                  <span style={{ fontSize: '12px' }}>📹</span>
                  {faceCount > 1 ? `MULTIPLE FACES (${faceCount}) ⚠️` : 'SINGLE FACE ✓'}
                </div>
                {!isInterviewee && (
                  <div style={{
                    backgroundColor: '#fef2f2',
                    color: '#dc2626',
                    border: '1px solid #fecaca',
                    padding: '6px 14px',
                    borderRadius: '6px',
                    fontSize: '0.7rem',
                    fontWeight: '700',
                    textTransform: 'uppercase',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                    marginTop: '8px',
                    backdropFilter: 'blur(4px)'
                  }}>
                    <span style={{ fontSize: '12px' }}>⚠️</span> UNKNOWN SPEAKER
                  </div>
                )}
              </div>

              {/* BOTTOM-RIGHT: EMOTION PILL */}
              <div style={{ position: 'absolute', bottom: '12px', right: '12px', zIndex: 10 }}>
                <div style={{
                  backgroundColor: 'rgba(255, 255, 255, 0.9)',
                  padding: '10px 16px',
                  borderRadius: '10px',
                  textAlign: 'center',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                  border: '1px solid rgba(255,255,255,0.8)',
                  backdropFilter: 'blur(8px)'
                }}>
                  <div style={{ fontSize: '0.85rem', color: '#1e293b', fontWeight: '800' }}>
                    {(hasSpeech || isActuallySpeaking) ? (dominantEmotion || 'NEUTRAL') : 'SILENT'}
                  </div>
                  <div style={{ fontSize: '0.55rem', color: '#64748b', marginTop: '2px' }}>
                    {(hasSpeech || isActuallySpeaking) ? (emotionConfidence > 0 ? `Confidence: ${emotionConfidence}%` : 'Voice detected...') : 'Waiting for voice...'}
                  </div>
                </div>
              </div>

              {/* BOTTOM-LEFT: SPEAKING NOW INDICATOR */}
              {showSpeakNow && (
                <div style={{ position: 'absolute', bottom: '12px', left: '12px', zIndex: 10 }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    backgroundColor: 'rgba(255,255,255,0.9)',
                    padding: '8px 14px',
                    borderRadius: '8px',
                    border: '1px solid rgba(255,255,255,0.8)',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
                  }}>
                    <span className="live-dot" style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      backgroundColor: '#ef4444',
                      animation: 'pulse 1.5s infinite'
                    }}></span>
                    <span style={{ color: '#1e293b', fontWeight: '800', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>SPEAKING NOW</span>
                  </div>
                </div>
              )}

            </div>

            <div className="response-area">
              {(interviewStage === 'listening_for_answer' || interviewStage === 'listening_for_start') ? (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', marginBottom: '15px' }}>
                    <div className="mic-status-container" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div className="mic-visualizer" style={{
                        width: '40px',
                        height: '40px',
                        borderRadius: '50%',
                        background: isActuallySpeaking ? 'rgba(239, 68, 68, 0.1)' : 'rgba(148, 163, 184, 0.1)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        position: 'relative'
                      }}>
                        <i className={`fa fa-microphone ${isActuallySpeaking ? 'pulse-red' : ''}`} style={{
                          color: isActuallySpeaking ? '#ef4444' : '#94a3b8',
                          fontSize: '1.2rem'
                        }}></i>
                        {/* Audio level circle */}
                        <div style={{
                          position: 'absolute',
                          inset: '-4px',
                          borderRadius: '50%',
                          border: '2px solid',
                          borderColor: isActuallySpeaking ? '#ef4444' : '#e2e8f0',
                          opacity: micLevel / 255,
                          transform: `scale(${1 + (micLevel / 255)})`,
                          transition: 'transform 0.1s ease',
                          pointerEvents: 'none'
                        }}></div>
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{
                          fontSize: '0.85rem',
                          fontWeight: 800,
                          color: isActuallySpeaking ? '#ef4444' : '#64748b',
                          letterSpacing: '0.5px'
                        }}>
                          {isActuallySpeaking ? 'RECORDING VOICE...' : 'LISTENING...'}
                        </span>
                        <div style={{
                          width: '100px',
                          height: '4px',
                          background: '#f1f5f9',
                          borderRadius: '2px',
                          marginTop: '4px',
                          overflow: 'hidden'
                        }}>
                          <div style={{
                            width: `${Math.min(micLevel * 1.5, 100)}%`,
                            height: '100%',
                            background: isActuallySpeaking ? '#ef4444' : '#94a3b8',
                            transition: 'width 0.1s ease'
                          }}></div>
                        </div>
                      </div>
                    </div>

                    {!isListening ? (
                      <button
                        onClick={startListening}
                        className="record-toggle-btn"
                        style={{
                          background: '#f8fafc',
                          border: '1px solid #e2e8f0',
                          color: '#475569',
                          padding: '8px 16px',
                          borderRadius: '8px',
                          fontSize: '0.8rem',
                          fontWeight: '700',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px'
                        }}
                      >
                        <i className="fa fa-play"></i> RESUME MIC
                      </button>
                    ) : (
                      <button
                        onClick={stopListeningAndSave}
                        className="record-toggle-btn"
                        style={{
                          background: '#fef2f2',
                          border: '1px solid #fecaca',
                          color: '#dc2626',
                          padding: '8px 16px',
                          borderRadius: '8px',
                          fontSize: '0.8rem',
                          fontWeight: '700',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px'
                        }}
                      >
                        <i className="fa fa-stop"></i> FINISH NOW
                      </button>
                    )}
                  </div>

                  <div className="transcript-box" style={{
                    position: 'relative',
                    background: '#ffffff',
                    borderRadius: '16px',
                    border: '1px solid #e2e8f0',
                    padding: '20px',
                    boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.02)',
                    minHeight: '80px'
                  }}>
                    <p style={{
                      margin: 0,
                      color: '#1e293b',
                      fontSize: '1rem',
                      fontWeight: '500',
                      lineHeight: '1.6'
                    }}>
                      {userAnswerSubtitle || (
                        <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>
                          Start speaking... If your voice is not appearing, try clicking "Resume Mic" or check your browser permissions.
                        </span>
                      )}
                    </p>

                    {isActuallySpeaking && (
                      <div className="typing-indicator" style={{
                        position: 'absolute',
                        bottom: '12px',
                        right: '16px',
                        display: 'flex',
                        gap: '3px'
                      }}>
                        <div className="dot"></div>
                        <div className="dot"></div>
                        <div className="dot"></div>
                      </div>
                    )}
                  </div>


                </>
              ) : interviewStage === 'question_speaking' ? (
                <div style={{ textAlign: 'center' }}>
                  <p style={{ margin: 0, color: '#16a34a', fontWeight: 700 }}>
                    <i className="fa fa-volume-up"></i> AI IS SPEAKING...
                  </p>
                  <p style={{ margin: 5, color: '#64748b', fontSize: '0.85rem' }}>Listen carefully to the question</p>
                </div>
              ) : (
                <div style={{ textAlign: 'center' }}>
                  <p style={{ margin: 0, color: '#8b5cf6', fontWeight: 700, marginBottom: '5px' }}>
                    {interviewStage === 'greeting' ? 'Interview will begin after the greeting...' :
                      interviewStage === 'processing' ? 'Processing Response...' : 'Waiting...'}
                  </p>
                  {userAnswerSubtitle && (
                    <p style={{ margin: 0, color: '#334155', fontSize: '1rem', fontStyle: 'italic', fontWeight: '500' }}>
                      "{userAnswerSubtitle}"
                    </p>
                  )}
                </div>
              )}

              {/* Submit Button - ALWAYS Show during listening stage to give user control */}
              {interviewStage === 'listening_for_answer' && (
                <button
                  className="submit-btn-dashboard"
                  onClick={stopListeningAndSave}
                  style={{
                    backgroundColor: userAnswerSubtitle ? 'var(--grade-primary)' : '#475569',
                    backgroundImage: userAnswerSubtitle ? 'var(--grade-primary)' : 'none',
                    cursor: userAnswerSubtitle ? 'pointer' : 'not-allowed',
                    opacity: 1,
                    marginTop: '15px'
                  }}
                  disabled={!userAnswerSubtitle && !isProcessing}
                >
                  Submit Answer <i className="fa fa-arrow-right"></i>
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Global Action: End Session below grid or in navbar? 
            Original had Logout in navbar. Reference image shows Logout in top right. 
            The Navbar component likely handles this, but let's add a button if needed. */}
        <div style={{ textAlign: 'center', marginTop: '20px' }}>
          <button className="logout-btn-dashboard" onClick={handleEndInterview}>
            End Interview Session
          </button>
        </div>

        {/* Setup Overlay */}
        {(!mediaInitialized || error) && (
          <div className="setup-overlay">
            {error ? (
              <div className="error-box">
                <p>{error}</p>
                <button onClick={initializeMedia} className="retry-btn">Retry Setup</button>
              </div>
            ) : (
              <div className="loading-box">
                <i className="fa fa-spinner fa-spin" style={{ fontSize: '2rem', color: '#6c5ce7', marginBottom: '15px' }}></i>
                <h3>Initializing Interview Environment</h3>
                <p>Please allow camera and microphone access in your browser.</p>
              </div>
            )}
          </div>
        )}
      </div >
    </>
  );
}

export default Interview