import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import Choice from './choice.jsx';
import Interview from './interview.jsx';
import Login from './login.jsx';
import Feedback from './pages/Feedback.jsx';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import './premium.css';
import './animations.css';
import ErrorBoundary from './components/ErrorBoundary.jsx';
import { ToastProvider } from './context/ToastContext.jsx';
import { GoogleOAuthProvider } from '@react-oauth/google';

ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
        <ErrorBoundary>
            <GoogleOAuthProvider clientId="584858872525-5lorrhd75kedfo0ho5u66ll1f92mnnk7.apps.googleusercontent.com">
                <ToastProvider>
                    <BrowserRouter>
                        <Routes>
                            <Route path="/choice" element={<Choice />} />
                            <Route path="/" element={<App />} />
                            <Route path="/interview" element={<Interview />} />
                            <Route path="/login" element={<Login />} />
                            <Route path="/feedback" element={<Feedback />} />
                        </Routes>
                    </BrowserRouter>
                </ToastProvider>
            </GoogleOAuthProvider>
        </ErrorBoundary>
    </React.StrictMode>
);
