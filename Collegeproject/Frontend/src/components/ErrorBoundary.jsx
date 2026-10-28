import React from 'react';

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false };
    }

    static getDerivedStateFromError() {
        return { hasError: true };
    }

    componentDidCatch(error, errorInfo) {
        console.error("ErrorBoundary caught an error", error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return this.props.fallback || <div style={{ padding: 20, textAlign: 'center' }}><h2>Something went wrong with the 3D view.</h2></div>;
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
