import { useState, useEffect } from 'react'
import './App.css'
import Login from './login.jsx'
import Interview from './interview.jsx';
import Navbar from './nav-bar.jsx';
import { Link, useNavigate } from 'react-router-dom';
import Background3D from './components/Background3D';
import SplineHero from './components/SplineHero';


function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const navigate = useNavigate();

  // Check authentication status on mount and when it changes
  useEffect(() => {
    const checkAuth = () => {
      const token = localStorage.getItem('token');
      setIsAuthenticated(!!token && token.trim() !== '' && token !== 'null' && token !== 'undefined');
    };

    // Check on mount
    checkAuth();

    // Listen for auth changes (login/logout events)
    window.addEventListener('authChange', checkAuth);
    window.addEventListener('storage', checkAuth);

    return () => {
      window.removeEventListener('authChange', checkAuth);
      window.removeEventListener('storage', checkAuth);
    };
  }, []);

  const handleStartClick = () => {
    // Check if user is authenticated
    const token = localStorage.getItem('token');
    const hasValidToken = token && token.trim() !== '' && token !== 'null' && token !== 'undefined';

    if (hasValidToken) {
      // User is logged in, go directly to form
      navigate('/choice');
    } else {
      // User is not logged in, redirect to login
      navigate('/login');
    }
  };

  return (
    <>
      <Background3D />

      {/* Nav-bar */}
      <Navbar />

      {/* Content */}
      <div className="hero-section">
        <div className="hero-text">
          <span className='small'><i className="fa fa-certificate" aria-hidden="true"></i>AIPowered Interview Practice</span>
          <h1 className='large'>Master Your Next <span className='interview'>Interview</span></h1>
          <p className='text'>Practice with our AI interviewer, get real-time feedback on your answers, body language, and voice tone. Build confidence and land your dream job.</p>

          <div className="button-group">
            <button onClick={handleStartClick} className="primary-btn">
              {isAuthenticated ? (
                <>Start Practice <i className="fa fa-long-arrow-right" aria-hidden="true"></i></>
              ) : (
                <>Login to Start <i className="fa fa-sign-in" aria-hidden="true"></i></>
              )}
            </button>
            {isAuthenticated && (
              <div className="logged-in-badge">
                <i className="fa fa-check-circle" aria-hidden="true"></i>
                <span>You're logged in</span>
              </div>
            )}
          </div>
        </div>

        <div className="hero-3d">
          <SplineHero />
        </div>
      </div>

      {/* Cards-- */}
      <div className='section-title'>
        <h2>Why Choose MockiT?</h2>
        <div className="underline"></div>
      </div>

      <div className="card-container">
        <div className="glass-card">
          <div className='icon-box'><i className="fa fa-comment" aria-hidden="true"></i></div>
          <span className='card-title'>Smart Question Generation</span>
          <span className='card-desc'>AI-powered questions tailored to your industry and role.</span>
        </div>

        <div className="glass-card">
          <div className='icon-box'><i className="fa fa-camera" aria-hidden="true"></i></div>
          <span className='card-title'>Body Language Analysis</span>
          <span className='card-desc'>Real-time feedback on posture, eye contact, and gestures.</span>
        </div>

        <div className="glass-card">
          <div className='icon-box'><i className="fa fa-pencil" aria-hidden="true"></i></div>
          <span className='card-title'>Answer Evaluation</span>
          <span className='card-desc'>Compare your responses with ideal answers and get scoring.</span>
        </div>

        <div className="glass-card">
          <div className='icon-box'><i className="fa fa-microphone" aria-hidden="true"></i></div>
          <span className='card-title'>Voice Emotion Detection</span>
          <span className='card-desc'>Analyze tone, pace, and confidence in your responses.</span>
        </div>
      </div>

      {/* Footer */}
      <footer className="footer-premium">
        <div className="footer-main">
          <div className="footer-brand">
            <span className="logo">MockiT</span>
            <p className="slogan">Master your next interview with AI-powered realism and real-time feedback.</p>
            <div className="social-links">
              <a href="#"><i className="fa fa-linkedin"></i></a>
              <a href="#"><i className="fa fa-twitter"></i></a>
              <a href="#"><i className="fa fa-github"></i></a>
            </div>
          </div>

          <div className="footer-links">
            <div className="link-group">
              <span className="footer-title">Product</span>
              <ul>
                <li><Link to="/">Home</Link></li>
                <li><Link to="/choice">Practice</Link></li>
                <li><Link to="/premium">Premium</Link></li>
              </ul>
            </div>

            <div className="link-group">
              <span className="footer-title">Company</span>
              <ul>
                <li><a href="#">About Us</a></li>
                <li><a href="#">Contact</a></li>
                <li><a href="#">Privacy Policy</a></li>
              </ul>
            </div>

            <div className="link-group">
              <span className="footer-title">Developed by</span>
              <ul className="developer-list">
                <li>Prayash Niraula</li>
                <li>Ranjit Adhikari</li>
                <li>Sarishma Neupane</li>
                <li>Sujit Adhikari</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="footer-bottom">
          <p>&copy; 2024 MockiT • Kathmandu, Nepal • All rights reserved.</p>
        </div>
      </footer>
    </>
  )
}

export default App