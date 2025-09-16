import React, { useState, useRef, useEffect } from 'react';
import { Input, Button } from 'antd';
import LoadingIndicator from './LoadingIndicator';
import './style.css';

interface Props {
    messages: string[];
    onSendMessage: (message: string) => void;
}

const ChatWindow: React.FC<Props> = ({ messages, onSendMessage }) => {
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);


    // 自动滚动到最新消息
    useEffect(() => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages]);

    const handleSend = async () => {
        if (!input.trim()) return;

        const text = input;
        setInput('');
        setIsLoading(true);

        try {
            await onSendMessage(text);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className="chat-window">
            <div className="messages-container">
                {messages.map((msg, index) => {
                    if (msg.includes('<a href=')) {
                        // 处理包含HTML的消息
                        const [prefix, htmlContent] = msg.split(': ', 2);
                        return (
                            <div key={index} className={prefix === 'User' ? 'user-message' : 'ai-message'}>
                                <strong>{prefix}:</strong> 
                                <span dangerouslySetInnerHTML={{ __html: htmlContent }} />
                            </div>
                        );
                    } else {
                        // 处理普通文本消息
                        return (
                            <div key={index} className={msg.startsWith('User') ? 'user-message' : 'ai-message'}>
                                {msg}
                            </div>
                        );
                    }
                })}
                {isLoading && <LoadingIndicator />}
                <div ref={messagesEndRef} />
            </div>

            <div className="input-area">
                <Input.TextArea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyUp={handleKeyPress}
                    placeholder="input message..."
                    autoSize={{ minRows: 1, maxRows: 4 }}
                    disabled={isLoading}
                />
                <Button
                    type="primary"
                    onClick={handleSend}
                    disabled={!input.trim() || isLoading}
                >
                    send
                </Button>
            </div>
        </div>
    );
};

export default ChatWindow;