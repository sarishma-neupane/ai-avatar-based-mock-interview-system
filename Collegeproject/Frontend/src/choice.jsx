import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from './nav-bar.jsx';
import './choice.css';
import Background3D from './components/Background3D';
import { generateInterviewQuestions } from './services/geminiService';
import { jobRoleMapping, jobRolesList } from './data/jobMapping';

function Choice() {
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    preferredJobRole: '',
    yearsOfExperience: '',
    focusAreas: [] // New field for multi-select
  });

  const [errors, setErrors] = useState({});
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationError, setGenerationError] = useState(null);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  // Check authentication status on mount - redirect to login if not authenticated
  useEffect(() => {
    const checkAuth = () => {
      const token = localStorage.getItem('token');
      if (!token || token.trim() === '' || token === 'null' || token === 'undefined') {
        setIsCheckingAuth(false);
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
              setIsCheckingAuth(false);
              navigate('/login');
              return;
            }
            // Token is valid - user is authenticated
            setIsCheckingAuth(false);
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
      setIsCheckingAuth(false);
      navigate('/login');
    };

    checkAuth();

    // Listen for auth changes
    const handleAuthChange = () => checkAuth();
    window.addEventListener('authChange', handleAuthChange);
    return () => window.removeEventListener('authChange', handleAuthChange);
  }, [navigate]);

  // Job Roles now imported from jobMapping.js
  const jobRoles = jobRolesList;

  const experienceOptions = [
    'Beginner',
    '1 year',
    '2 years',
    '3 years',
    '4 years',
    '5+ years'
  ];

  const handleInputChange = (e) => {
    const { name, value } = e.target;

    if (name === 'preferredJobRole') {
      // Reset focus areas when job role changes
      setFormData({ ...formData, [name]: value, focusAreas: [] });
    } else {
      setFormData({ ...formData, [name]: value });
    }

    // Clear error for this field when user starts typing
    if (errors[name]) {
      setErrors({ ...errors, [name]: '' });
    }
  };

  const handleFocusAreaChange = (area) => {
    const currentAreas = [...formData.focusAreas];
    const index = currentAreas.indexOf(area);

    if (index > -1) {
      currentAreas.splice(index, 1);
    } else {
      currentAreas.push(area);
    }

    setFormData({ ...formData, focusAreas: currentAreas });

    if (errors.focusAreas) {
      setErrors({ ...errors, focusAreas: '' });
    }
  };


  const validateForm = () => {
    const newErrors = {};

    if (!formData.firstName.trim()) {
      newErrors.firstName = 'First name is required';
    }

    if (!formData.lastName.trim()) {
      newErrors.lastName = 'Last name is required';
    }

    if (!formData.preferredJobRole) {
      newErrors.preferredJobRole = 'Preferred job role is required';
    }

    if (!formData.yearsOfExperience) {
      newErrors.yearsOfExperience = 'Years of experience is required';
    }

    if (formData.preferredJobRole && formData.focusAreas.length === 0) {
      newErrors.focusAreas = 'Please select at least one focus area';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    // Check if user is logged in
    localStorage.getItem('token');

    // Generate session ID
    const sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

    // Clear old interview data
    localStorage.removeItem('generatedQuestions');
    localStorage.removeItem('idealAnswers');
    localStorage.removeItem('preloadedNextQuestion');
    localStorage.removeItem('currentSessionId');
    localStorage.removeItem('questionSessionId');

    // Store form data in localStorage
    const candidateInfo = {
      ...formData,
      sessionId: sessionId
    };
    localStorage.setItem('candidateInfo', JSON.stringify(candidateInfo));

    // Generate interview questions using Gemini
    setIsGenerating(true);
    setGenerationError(null);

    try {
      const candidateName = `${formData.firstName} ${formData.lastName}`;
      const result = await generateInterviewQuestions({
        jobRole: formData.preferredJobRole,
        yearsOfExperience: formData.yearsOfExperience,
        candidateName: candidateName,
        sessionId: sessionId,
        focusAreas: formData.focusAreas // Pass new field
      });

      console.log('Question generation result:', result);
      console.log('Result success:', result.success);
      console.log('Result data:', result.data);

      if (result.success) {
        console.log('Success! Storing questions and navigating...');
        // Store generated questions and ideal answers
        localStorage.setItem('generatedQuestions', JSON.stringify(result.data.questions));
        if (result.data.ideal_answers) {
          localStorage.setItem('idealAnswers', JSON.stringify(result.data.ideal_answers));
        }
        if (result.data.preloaded_next_question) {
          localStorage.setItem('preloadedNextQuestion', JSON.stringify(result.data.preloaded_next_question));
        }
        localStorage.setItem('questionSessionId', sessionId);

        console.log('Navigating to /interview...');
        // After form submission, always go to interview (user is already authenticated if they reached here)
        try {
          navigate('/interview');
          // Fallback: force navigation if react-router fails
          setTimeout(() => {
            if (window.location.pathname !== '/interview') {
              console.warn('React Router navigation failed, using window.location...');
              window.location.href = '/interview';
            }
          }, 100);
        } catch (navError) {
          console.error('Navigation error:', navError);
          window.location.href = '/interview';
        }
      } else {
        console.error('Generation failed:', result.error);
        setGenerationError(result.error || 'Failed to generate questions. Please try again.');
        setIsGenerating(false);
      }
    } catch (error) {
      console.error('Error generating questions:', error);
      let errorMsg = 'An error occurred while generating questions. ';

      // Check for rate limit error
      if (error.response && error.response.status === 500) {
        errorMsg = '⚠️ API Rate Limit Exceeded! The Gemini API free tier allows only 5 requests per minute. Please wait 60 seconds and try again.';
      } else if (error.message && error.message.includes('ECONNREFUSED')) {
        errorMsg += 'Please make sure the Django backend server is running on http://localhost:8000';
      } else {
        errorMsg += 'Please try again.';
      }

      setGenerationError(errorMsg);
      setIsGenerating(false);
    }
  };

  // Show loading while checking authentication
  if (isCheckingAuth) {
    return (
      <>
        <Navbar />
        <div className="choice-container">
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <i className="fa fa-spinner fa-spin" style={{ fontSize: '24px', marginBottom: '20px' }}></i>
            <p>Checking authentication...</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Background3D />
      {/* Nav-bar */}
      <Navbar minimal={true} />

      {/* Content */}
      <div className="choice-container">
        <div className="choice-header">
          <h1 className="choice-title">Interview Setup</h1>
          <p className="choice-subtitle">Please provide your information to start the interview</p>
        </div>

        <div className="choice-form-wrapper">
          <form className="choice-form" onSubmit={handleSubmit}>
            {/* First Name */}
            <div className="form-field">
              <label htmlFor="firstName">First Name *</label>
              <input
                type="text"
                id="firstName"
                name="firstName"
                value={formData.firstName}
                onChange={handleInputChange}
                placeholder="Enter your first name"
                className={errors.firstName ? 'error' : ''}
              />
              {errors.firstName && <span className="error-message">{errors.firstName}</span>}
            </div>

            {/* Last Name */}
            <div className="form-field">
              <label htmlFor="lastName">Last Name *</label>
              <input
                type="text"
                id="lastName"
                name="lastName"
                value={formData.lastName}
                onChange={handleInputChange}
                placeholder="Enter your last name"
                className={errors.lastName ? 'error' : ''}
              />
              {errors.lastName && <span className="error-message">{errors.lastName}</span>}
            </div>

            {/* Preferred Job Role */}
            <div className="form-field">
              <label htmlFor="preferredJobRole">Preferred Job Role *</label>
              <select
                id="preferredJobRole"
                name="preferredJobRole"
                value={formData.preferredJobRole}
                onChange={handleInputChange}
                className={errors.preferredJobRole ? 'error' : ''}
              >
                <option value="">Select your preferred job role</option>
                {jobRoles.map((role, index) => (
                  <option key={index} value={role}>
                    {role}
                  </option>
                ))}
              </select>
              {errors.preferredJobRole && <span className="error-message">{errors.preferredJobRole}</span>}
            </div>

            {/* Focus Areas (Conditional) */}
            {formData.preferredJobRole && jobRoleMapping[formData.preferredJobRole] && (
              <div className="form-field">
                <label>Focus Areas * <small style={{ fontWeight: 'normal', fontSize: '12px' }}>(Select multiple)</small></label>
                <div className="focus-areas-grid">
                  {jobRoleMapping[formData.preferredJobRole].map((area) => (
                    <div
                      key={area}
                      className={`focus-area-chip ${formData.focusAreas.includes(area) ? 'active' : ''}`}
                      onClick={() => handleFocusAreaChange(area)}
                    >
                      {area}
                      {formData.focusAreas.includes(area) && <i className="fa fa-check-circle" style={{ marginLeft: '8px' }}></i>}
                    </div>
                  ))}
                </div>
                {errors.focusAreas && <span className="error-message" style={{ display: 'block', marginTop: '5px' }}>{errors.focusAreas}</span>}
              </div>
            )}

            {/* Years of Experience */}
            <div className="form-field">
              <label htmlFor="yearsOfExperience">Years of Experience *</label>
              <select
                id="yearsOfExperience"
                name="yearsOfExperience"
                value={formData.yearsOfExperience}
                onChange={handleInputChange}
                className={errors.yearsOfExperience ? 'error' : ''}
              >
                <option value="">Select years of experience</option>
                {experienceOptions.map((exp, index) => (
                  <option key={index} value={exp}>
                    {exp}
                  </option>
                ))}
              </select>
              {errors.yearsOfExperience && <span className="error-message">{errors.yearsOfExperience}</span>}
            </div>

            {/* Error Message */}
            {generationError && (
              <div className="error-message" style={{
                marginBottom: '15px',
                padding: '16px',
                background: '#fee',
                border: '2px solid #fcc',
                borderRadius: '8px',
                color: '#c33',
                fontSize: '14px',
                lineHeight: '1.6'
              }}>
                <div style={{ fontWeight: 'bold', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <i className="fa fa-exclamation-triangle" aria-hidden="true"></i>
                  Error Generating Questions
                </div>
                <div>{generationError}</div>
                {generationError.includes('localhost:8000') && (
                  <div style={{ marginTop: '12px', padding: '10px', background: '#fff', borderRadius: '4px', fontSize: '13px' }}>
                    <strong>Quick Fix:</strong>
                    <ol style={{ marginTop: '8px', marginLeft: '20px' }}>
                      <li>Open a terminal</li>
                      <li>Navigate to: <code style={{ background: '#f0f0f0', padding: '2px 6px', borderRadius: '3px' }}>cd Backend</code></li>
                      <li>Run: <code style={{ background: '#f0f0f0', padding: '2px 6px', borderRadius: '3px' }}>python manage.py runserver</code></li>
                      <li>Wait for "Starting development server" message</li>
                      <li>Click "Continue to Interview" again</li>
                    </ol>
                  </div>
                )}
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              className="submit-btn"
              disabled={isGenerating}
            >
              {isGenerating ? (
                <>
                  <i className="fa fa-spinner fa-spin" aria-hidden="true"></i> Generating Questions...
                </>
              ) : (
                <>
                  Continue to Interview <i className="fa fa-arrow-right" aria-hidden="true"></i>
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </>
  );
}

export default Choice;
