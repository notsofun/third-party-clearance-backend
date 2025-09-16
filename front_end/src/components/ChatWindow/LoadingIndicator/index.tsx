// src/components/ChatWindow/LoadingIndicator/index.tsx
import React from 'react';
import './style.css';

const LoadingIndicator: React.FC = () => {
    return (
        <div className="loading-indicator">
            <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
            <div className="typing-text">AI is thinking...</div>
        </div>
    );
};

export default LoadingIndicator;