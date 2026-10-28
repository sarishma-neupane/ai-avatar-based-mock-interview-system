import React, { useState, useEffect } from 'react';
import './nav-bar.css';
import { Link, useNavigate } from 'react-router-dom';

function Navbar({ minimal = false }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [showLogoutMessage, setShowLogoutMessage] = useState(false);
  const navigate = useNavigate();

  // Check authentication status
  useEffect(() => {
    const checkAuth = () => {
      const token = localStorage.getItem('token');
      setIsAuthenticated(!!token && token.trim() !== '');
    };

    // Check on mount
    checkAuth();

    // Listen for storage changes (in case user logs in/out in another tab)
    window.addEventListener('storage', checkAuth);

    // Also check on focus (when user switches back to tab)
    window.addEventListener('focus', checkAuth);

    // Listen for custom event when login/logout happens in same tab
    window.addEventListener('authChange', checkAuth);

    return () => {
      window.removeEventListener('storage', checkAuth);
      window.removeEventListener('focus', checkAuth);
      window.removeEventListener('authChange', checkAuth);
    };
  }, []);

  const handleLogout = () => {
    // Clear tokens
    localStorage.removeItem('token');
    localStorage.removeItem('refreshToken');
    setIsAuthenticated(false);

    // Dispatch custom event to notify other components
    window.dispatchEvent(new Event('authChange'));

    // Show success message
    setShowLogoutMessage(true);

    // Hide message after 3 seconds
    setTimeout(() => {
      setShowLogoutMessage(false);
    }, 3000);

    // Redirect to home page
    navigate('/');
  };

  if (minimal) {
    if (!isAuthenticated) return null; // Don't show anything if not logged in on minimal pages
    return (
      <>
        <div style={{ position: 'fixed', top: '24px', right: '32px', zIndex: 1000 }}>
          <button onClick={handleLogout} className='login logout-btn'>
            Logout
          </button>
        </div>
        {/* Logout success message */}
        {showLogoutMessage && (
          <div className="logout-message">
            Successfully logged out
          </div>
        )}
      </>
    );
  }

  return (
    <nav>
      <div className="logo">
        <span>MockiT</span>
      </div>

      <div className="nav-links">
        <ul>

          <li>
            {isAuthenticated ? (
              <button onClick={handleLogout} className='login logout-btn'>
                Logout
              </button>
            ) : (
              <Link to='/login' className='login'>Login</Link>
            )}
          </li>
        </ul>
      </div>

      {/* Logout success message */}
      {showLogoutMessage && (
        <div className="logout-message">
          Successfully logged out
        </div>
      )}
    </nav>
  );
}

export default Navbar;
