import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import './login.css';
import Background3D from './components/Background3D';
import { GoogleLogin } from '@react-oauth/google';

function Login() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('token'));
  const [isLoading, setIsLoading] = useState(true);
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    password2: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  // Check authentication status on mount
  useEffect(() => {
    const verifyToken = async () => {
      const token = localStorage.getItem('token');
      if (token && token.trim() !== '') {
        try {
          // Optional: Add token verification endpoint if available
          setIsAuthenticated(true);
        } catch {
          localStorage.removeItem('token');
          setIsAuthenticated(false);
        }
      }
      setIsLoading(false);
    };
    verifyToken();
  }, []);

  const handleInputChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    if (formData.password !== formData.password2) {
      setError('Passwords do not match');
      setLoading(false);
      return;
    }

    try {
      await axios.post('http://localhost:8000/api/accounts/register/', {
        username: formData.username,
        email: formData.email,
        password: formData.password,
        password2: formData.password2
      }, {
        headers: {
          'Content-Type': 'application/json',
        }
      });

      // After successful registration, automatically log in the user
      try {
        const loginResponse = await axios.post('http://localhost:8000/api/accounts/login/', {
          username: formData.username,
          password: formData.password
        }, {
          headers: {
            'Content-Type': 'application/json',
          }
        });

        const accessToken = loginResponse.data.access;
        const refreshToken = loginResponse.data.refresh;
        if (accessToken) {
          localStorage.setItem('token', accessToken);
          localStorage.setItem('refreshToken', refreshToken);
          localStorage.setItem('user', JSON.stringify({ username: formData.username }));
        }
        setIsAuthenticated(true);
        window.dispatchEvent(new Event('authChange'));
        navigate('/choice', { replace: true });
      } catch {
        setError('Registration successful. Please log in.');
        setIsLogin(true);
      }

      setFormData({ username: '', email: '', password: '', password2: '' });
    } catch (err) {
      setError(err.response?.data?.message || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await axios.post('http://localhost:8000/api/accounts/login/', {
        username: formData.username,
        password: formData.password
      }, {
        headers: {
          'Content-Type': 'application/json',
        }
      });

      const accessToken = response.data.access;
      const refreshToken = response.data.refresh;
      if (accessToken) {
        localStorage.setItem('token', accessToken);
        localStorage.setItem('refreshToken', refreshToken);
        localStorage.setItem('user', JSON.stringify({ username: formData.username }));
      }
      setFormData({ username: '', email: '', password: '', password2: '' });
      setIsAuthenticated(true);
      window.dispatchEvent(new Event('authChange'));
      navigate('/choice', { replace: true });
    } catch (err) {
      setError(err.response?.data?.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  if (isLoading) {
    return <div className="form-container">Loading...</div>;
  }

  return (
    <>
      <Background3D />
      <div className="form-container">
        {!isAuthenticated && (
          <>
            <span className="title">MockiT</span>
            <span className="sub-title">
              {isLogin ? 'Login to begin interview session' : 'Register to start your journey'}
            </span>
            <div className="formbox">
              {error && (
                <div style={{ color: 'red', marginBottom: '10px' }}>{error}</div>
              )}
              <form action="#">
                {isLogin ? (
                  <>
                    <input
                      type="text"
                      name="username"
                      value={formData.username}
                      onChange={handleInputChange}
                      placeholder="Username"
                      className="writable"
                      required
                    />
                    <input
                      type="password"
                      name="password"
                      value={formData.password}
                      onChange={handleInputChange}
                      placeholder="Password"
                      className="writable"
                      required
                    />
                  </>
                ) : (
                  <>
                    <input
                      type="text"
                      name="username"
                      value={formData.username}
                      onChange={handleInputChange}
                      placeholder="Username"
                      className="writable"
                      required
                    />
                    <input
                      type="email"
                      name="email"
                      value={formData.email}
                      onChange={handleInputChange}
                      placeholder="Email"
                      className="writable"
                      required
                    />
                    <input
                      type="password"
                      name="password"
                      value={formData.password}
                      onChange={handleInputChange}
                      placeholder="Password"
                      className="writable"
                      required
                    />
                    <input
                      type="password"
                      name="password2"
                      value={formData.password2}
                      onChange={handleInputChange}
                      placeholder="Confirm Password"
                      className="writable"
                      required
                    />
                  </>
                )}

                <input
                  type="submit"
                  value={loading ? 'Processing...' : isLogin ? 'Login' : 'Register'}
                  className="submit"
                  onClick={isLogin ? handleLogin : handleRegister}
                  disabled={loading}
                />
              </form>
              <button
                onClick={() => setIsLogin(!isLogin)}
                className="submit"
              >
                {isLogin ? 'Do not have an account?' : 'Already have an account?'}
              </button>

              <div className="google-login-wrapper" style={{ marginTop: '20px', display: 'flex', justifyContent: 'center' }}>
                <GoogleLogin
                  onSuccess={async (credentialResponse) => {
                    console.log(credentialResponse);
                    try {
                      setLoading(true);
                      const res = await axios.post('http://localhost:8000/api/accounts/google-login/', {
                        token: credentialResponse.credential
                      });

                      const accessToken = res.data.access;
                      const refreshToken = res.data.refresh;
                      if (accessToken) {
                        localStorage.setItem('token', accessToken);
                        localStorage.setItem('refreshToken', refreshToken);
                        localStorage.setItem('user', JSON.stringify({ username: res.data.username }));
                      }
                      setIsAuthenticated(true);
                      window.dispatchEvent(new Event('authChange'));
                      navigate('/choice', { replace: true });
                    } catch (err) {
                      console.error('Google Login Error:', err);
                      setError('Google Login failed. Please try again.');
                    } finally {
                      setLoading(false);
                    }
                  }}
                  onError={() => {
                    console.log('Login Failed');
                    setError('Google Login Failed');
                  }}
                  useOneTap
                  theme="filled_black"
                  shape="pill"
                />
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}

export default Login;
