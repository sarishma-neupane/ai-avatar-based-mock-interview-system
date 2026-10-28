import React, { createContext, useContext, useState, useCallback } from 'react';
import '../components/Toast.css';

const ToastContext = createContext();

export const useToast = () => {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error('useToast must be used within a ToastProvider');
    }
    return context;
};

export const ToastProvider = ({ children }) => {
    const [toasts, setToasts] = useState([]);

    const removeToast = useCallback((id) => {
        setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, []);

    const addToast = useCallback((message, type = 'info', duration = 3000) => {
        const id = Date.now().toString() + Math.random();

        // Handle title vs message object
        let title = '';
        let desc = message;

        if (typeof message === 'object') {
            title = message.title || '';
            desc = message.description || message.message || '';
        } else {
            // Auto-capitalized title based on type (if only string provided)
            title = type.charAt(0).toUpperCase() + type.slice(1);
        }

        setToasts((prev) => [...prev, { id, title, desc, type, duration }]);

        if (duration > 0) {
            setTimeout(() => {
                removeToast(id);
            }, duration);
        }
    }, [removeToast]);

    const success = (msg, duration) => addToast(msg, 'success', duration);
    const error = (msg, duration) => addToast(msg, 'error', duration);
    const info = (msg, duration) => addToast(msg, 'info', duration);
    const warning = (msg, duration) => addToast(msg, 'warning', duration);

    return (
        <ToastContext.Provider value={{ addToast, removeToast, success, error, info, warning }}>
            {children}
            <div className="toast-container">
                {toasts.map((toast) => (
                    <ToastItem key={toast.id} toast={toast} onRemove={removeToast} />
                ))}
            </div>
        </ToastContext.Provider>
    );
};

const ToastItem = ({ toast, onRemove }) => {
    const [isExiting, setIsExiting] = useState(false);

    const handleClose = (e) => {
        e.stopPropagation();
        setIsExiting(true);
        setTimeout(() => onRemove(toast.id), 300); // Wait for animation
    };

    // Icons based on type
    const getIcon = () => {
        switch (toast.type) {
            case 'success': return <i className="fa fa-check-circle" />;
            case 'error': return <i className="fa fa-exclamation-circle" />;
            case 'warning': return <i className="fa fa-exclamation-triangle" />;
            default: return <i className="fa fa-info-circle" />;
        }
    };

    return (
        <div
            className={`toast-message ${toast.type} ${isExiting ? 'toast-hidden' : ''}`}
            onClick={handleClose}
        >
            <div className="toast-icon">
                {getIcon()}
            </div>
            <div className="toast-content">
                {toast.title && <div className="toast-title">{toast.title}</div>}
                <div className="toast-desc">{toast.desc}</div>
            </div>
            <button className="toast-close" onClick={handleClose}>
                <i className="fa fa-times" />
            </button>
        </div>
    );
};

export default ToastProvider;
