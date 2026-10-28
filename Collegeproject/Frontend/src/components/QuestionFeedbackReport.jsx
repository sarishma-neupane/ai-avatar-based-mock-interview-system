import React from 'react';
import './QuestionFeedbackReport.css';

function QuestionFeedbackReport({ feedbackData, candidateName, jobRole }) {
    if (!feedbackData || feedbackData.length === 0) {
        return (
            <div className="feedback-report-empty">
                <p>No detailed feedback available yet.</p>
                <p className="feedback-hint">Complete the interview to see question-wise feedback with scores!</p>
            </div>
        );
    }

    return (
        <div className="question-feedback-report">
            {/* Report Header as per Image */}
            <div className="report-main-header">
                <div className="candidate-meta">
                    <p><strong>Candidate Name:</strong> {candidateName || 'N/A'}</p>
                    <p><strong>Job Role:</strong> {jobRole || 'N/A'}</p>
                </div>
                <h2 className="report-title">Question-wise Feedback</h2>
            </div>

            <div className="feedback-linear-list">
                {feedbackData.map((feedback, index) => {
                    const metrics = feedback.metrics || {};
                    return (
                        <div key={index} className="feedback-linear-item">
                            <h3 className="linear-question-no">Q. NO {feedback.question_no || index + 1}</h3>

                            <div className="linear-content-row">
                                <div className="linear-label">Question:</div>
                                <div className="linear-value question-text-box">{feedback.question}</div>
                            </div>

                            <div className="linear-content-row">
                                <div className="linear-label">Your answer:</div>
                                <div className="linear-value user-text-box">{feedback.user_answer}</div>
                            </div>

                            <div className="linear-content-row">
                                <div className="linear-label">Ideal answer: <span className="hint-text">(The one with highest semantic)</span></div>
                                <div className="linear-value ideal-text-box">{feedback.ideal_answer}</div>
                            </div>

                            {/* Metrics Horizontal List */}
                            <div className="linear-metrics-bar">
                                <div className="metric-tag">
                                    <span className="m-label">Semantic score:</span>
                                    <span className="m-value">{((metrics.semantic_score || 0) * 100).toFixed(0)}%</span>
                                </div>
                                <div className="metric-tag">
                                    <span className="m-label">Body posture:</span>
                                    <span className="m-value">{metrics.posture || 'N/A'}</span>
                                </div>
                                <div className="metric-tag">
                                    <span className="m-label">Emotion:</span>
                                    <span className="m-value">{metrics.emotion || 'N/A'}</span>
                                </div>
                                <div className="metric-tag">
                                    <span className="m-label">Multiple speak count:</span>
                                    <span className="m-value">{metrics.speaker_flags || 0}</span>
                                </div>
                                <div className="metric-tag">
                                    <span className="m-label">Multiple faces detection count:</span>
                                    <span className="m-value">{metrics.face_flags || 0}</span>
                                </div>
                                <div className="metric-tag">
                                    <span className="m-label">Tab switches / Screen activity:</span>
                                    <span className="m-value">{metrics.tab_switches || 0}</span>
                                </div>
                            </div>

                            {/* Feedback Points */}
                            <div className="linear-feedback-points">
                                <div className="points-column">
                                    <h4 className="pos-title">Key positives</h4>
                                    <ul>
                                        {(feedback.positives || []).map((p, i) => (
                                            <li key={i}>{p}</li>
                                        ))}
                                    </ul>
                                </div>
                                <div className="points-column">
                                    <h4 className="neg-title">Negatives</h4>
                                    <ul>
                                        {(feedback.negatives || []).map((n, i) => (
                                            <li key={i}>{n}</li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                            <hr className="item-divider" />
                        </div>
                    );
                })}
            </div>
        </div >
    );
}

export default QuestionFeedbackReport;
