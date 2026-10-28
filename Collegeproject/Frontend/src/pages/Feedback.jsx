import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import Navbar from '../nav-bar.jsx';
import './Feedback.css';
import QuestionFeedbackReport from '../components/QuestionFeedbackReport';
import axios from 'axios';

function Feedback() {
    const location = useLocation();
    const navigate = useNavigate();

    // Get session_id and passed question feedback from navigation state
    const { sessionId, questionFeedback: passedQuestionFeedback } = location.state || {};
    const localSessionId = sessionId || localStorage.getItem('currentSessionId');

    const [feedback, setFeedback] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Get API base URL from env
    const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

    useEffect(() => {
        if (!localSessionId) {
            setError("No interview session found. Please ensure you finished the interview.");
            setLoading(false);
            return;
        }

        const fetchFeedback = async () => {
            try {
                console.log(`[FEEDBACK] Fetching report for session: ${localSessionId}`);
                const token = localStorage.getItem('token');
                const headers = { 'Content-Type': 'application/json' };
                if (token && token !== 'null' && token !== 'undefined') {
                    headers['Authorization'] = `Bearer ${token}`;
                }

                const response = await axios.post(`${API_BASE_URL}/api/gemini/feedback/`,
                    { session_id: localSessionId },
                    {
                        headers,
                        timeout: 300000 // Increased to 5 minutes to prevent local/network timeouts for AI reports
                    }
                );

                console.log("[FEEDBACK] Data Received:", response.data);

                if (response.data.success && response.data.feedback) {
                    setFeedback(response.data.feedback);
                } else {
                    throw new Error(response.data.error || "Feedback data missing from response");
                }
            } catch (err) {
                console.error("[FEEDBACK] Fetch Error:", err);
                const errorMsg = err.response?.data?.error || err.message || 'Failed to generate feedback report';
                const errorDetail = err.response?.data?.details || err.code || '';
                setError(`${errorMsg} ${errorDetail ? '(' + errorDetail + ')' : ''}`);
            } finally {
                setLoading(false);
            }
        };

        fetchFeedback();
    }, [localSessionId]);

    const handleHomeClick = () => {
        navigate('/');
    };

    if (loading) {
        return (
            <div className="feedback-container loading-state">
                <Navbar />
                <div className="loading-content">
                    <i className="fa fa-spinner fa-spin fa-3x"></i>
                    <h2>Generating your Personalized Interview Report AI...</h2>
                    <p>Analyzing your answers, voice tone, and body language.</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="feedback-container error-state">
                <Navbar />
                <div className="error-content">
                    <i className="fa fa-exclamation-triangle fa-3x"></i>
                    <h2>Oops! Something went wrong.</h2>
                    <p>{error}</p>
                    <div className="error-actions">
                        <button onClick={() => window.location.reload()} className="retry-btn">
                            <i className="fa fa-refresh"></i> Retry Generation
                        </button>
                        <button onClick={handleHomeClick} className="home-btn">Go Home</button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <>
            <Navbar />
            <div className="feedback-container">
                <div className="feedback-header">
                    <h1>Interview Performance Report</h1>
                    {feedback.candidate_name && (
                        <div className="candidate-info-banner">
                            <p><strong>Candidate:</strong> {feedback.candidate_name}</p>
                            <p><strong>Role:</strong> {feedback.job_role}</p>
                        </div>
                    )}
                    <p className="session-id">Session ID: {localSessionId}</p>
                </div>

                <div className="score-card">
                    <div className="score-circle">
                        <span className="score-value">{feedback.score}</span>
                        <span className="score-max">/100</span>
                    </div>
                    <div className="score-summary">
                        <h3>Overall Performance</h3>
                        <p>{feedback.summary}</p>
                    </div>
                </div>

                <div className="feedback-grid">
                    <div className="feedback-section positives">
                        <h2><i className="fa fa-thumbs-up"></i> Key Strengths</h2>
                        <ul>
                            {(feedback?.positives || []).map((point, index) => (
                                <li key={index}>{point}</li>
                            ))}
                        </ul>
                    </div>

                    <div className="feedback-section negatives">
                        <h2><i className="fa fa-lightbulb-o"></i> Areas for Improvement</h2>
                        <ul>
                            {(feedback?.negatives || []).map((point, index) => (
                                <li key={index}>{point}</li>
                            ))}
                        </ul>
                    </div>
                </div>

                {/* NEW: Detailed Question-Wise Feedback Report */}
                <QuestionFeedbackReport
                    feedbackData={feedback.question_breakdown}
                    candidateName={feedback.candidate_name}
                    jobRole={feedback.job_role}
                />

                <div className="action-area">
                    <button onClick={handleHomeClick} className="home-btn">
                        Back to Dashboard
                    </button>
                </div>
            </div>
        </>
    );
}

export default Feedback;
