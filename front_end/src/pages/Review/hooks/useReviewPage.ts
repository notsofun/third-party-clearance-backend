import { useState, useCallback } from 'react';
import { message } from 'antd';
import { Component, ChatResponse, AnalyzeResponse, SuccessResponse, ComplexMessage } from '../../../services/types';
import { sendMessage, API_BASE } from '../../../services/api';
import { UPLOAD_STATUS, CHAT_STATUS, UploadStatus} from '../../../constants';

interface UseReviewPageReturn {
    // 状态
    uploadStatus: UploadStatus;
    sessionId: string;
    components: Component[];
    messages: string[];
    currentPhase: 'license' | 'contract';

    // 操作函数
    handleFileAnalyzed: (response: AnalyzeResponse) => void;
    handleContractAnalyzed: (response: SuccessResponse) => void;
    handleSendMessage: (text: string) => Promise<void>;
    resetToContractUpload: () => void;
}

export const useReviewPage = (): UseReviewPageReturn => {
    const [uploadStatus, setUploadStatus] = useState<UploadStatus>(UPLOAD_STATUS.IDLE);
    const [sessionId, setSessionId] = useState<string>('');
    const [components, setComponents] = useState<Component[]>([]);
    const [messages, setMessages] = useState<string[]>([]);
    const [ ,setSuccess] = useState<boolean>();
    const [currentPhase, setCurrentPhase] = useState<'license' | 'contract'>('license');

    const handleFileAnalyzed = useCallback((response: AnalyzeResponse) => {
        const { session_id, components, message: msg } = response;

        setSessionId(session_id);
        setComponents(components);
        setMessages([msg || 'Analysis finished, please start checking licenses...']);
        setUploadStatus(UPLOAD_STATUS.ANALYZED);
        console.log('文件分析成功');
    }, []);

    const handleContractAnalyzed = useCallback((response: SuccessResponse) => {
        const {success, message} = response;

        setSuccess(success);
        setUploadStatus(UPLOAD_STATUS.ANALYZED);
        const aiMessage = normalizeMessages(message);
        if (aiMessage.length > 0) {
            aiMessage.forEach(msg => {
                setMessages(prev => [...prev, `AI: ${msg}`]);
            });
        }
        console.log('合同分析成功')
    }, []);

    const formatObjectMessage = (obj: any, prefix: string = ""): string[] => {
        const messages: string[] = [];
        
        const formatValue = (key: string, value: any, indent: string = ""): void => {
            if (typeof value === 'string') {
                messages.push(`${indent}**${key}**: ${value}`);
            } else if (Array.isArray(value)) {
                messages.push(`${indent}**${key}**:`);
                value.forEach((item, index) => {
                    if (typeof item === 'string') {
                        messages.push(`${indent}   ${index + 1}. ${item}`);
                    } else {
                        messages.push(`${indent}   ${index + 1}. ${JSON.stringify(item)}`);
                    }
                });
            } else if (typeof value === 'object' && value !== null) {
                messages.push(`${indent}**${key}**:`);
                Object.entries(value).forEach(([subKey, subValue]) => {
                    formatValue(subKey, subValue, indent + "   ");
                });
            } else {
                messages.push(`${indent}**${key}**: ${String(value)}`);
            }
        };
        
        Object.entries(obj).forEach(([key, value]) => {
            formatValue(key, value, prefix);
        });
        
        return messages;
    };

    // 更通用的消息标准化函数
    const normalizeMessages = (message: string | string[] | ComplexMessage | undefined): string[] => {
        if (typeof message === 'string') {
            return [message];
        }
        
        if (Array.isArray(message)) {
            return message;
        }
        
        if (typeof message === 'object' && message !== null) {
            // 首先尝试特定的格式化（如 OSS_Risks）
            if ('OSS_Risks' in message) {
                return formatObjectMessage(message);
            }
            
            // 如果没有特定格式，使用通用格式化
            return formatObjectMessage(message);
        }
        
        return ['收到了无法解析的消息格式'];
    };

    const handleSendMessage = useCallback(async (text: string) => {
        if (!sessionId) return;

        try {
            setMessages(prev => [...prev, `User: ${text}`]);

            const response: ChatResponse = await sendMessage(sessionId, text);
            console.log("AI response:", response);

            // 处理AI消息 - 使用改进的标准化函数
            const aiMessages = normalizeMessages(response.message);
            console.log('this is my ai Messages', aiMessages)
            if (aiMessages.length > 0) {
                aiMessages.forEach(msg => {
                    setMessages(prev => [...prev, `AI: ${msg}`]);
                });
            }
            
            // 前端刷新的时候后端的状态不会更新
            console.log('现在的状态是：', response.status);
            
            // 处理状态变化
            switch (response.status) {
                case CHAT_STATUS.COMPLETED:
                    message.success('所有组件已确认完成！');
                    // 检查是否有下载链接
                    if (response.download && response.download.available) {
                        // 添加下载按钮消息
                        console.log('now we have the link for downloading...', response)
                        setMessages(prev => [
                            ...prev,
                            `AI: Please click to view the oss readme file：<a href="${API_BASE}/${response.download?.url}" download="${API_BASE}/${response.download?.url}" class="download-link">Download</a>`
                        ]);
                    }
                    break;
                case CHAT_STATUS.TO_CONTRACT:
                    setCurrentPhase('contract');
                    setUploadStatus(UPLOAD_STATUS.CONTRACT);
                    console.log('请上传合同文件进行下一步分析');
                    break;
                default:
                    // 继续当前流程
                    break;
            }
        } catch (error) {
            message.error('发送消息失败');
            setMessages(prev => [...prev, 'AI: Sorry, something went wrong. Please try again later.']);
        }
    }, [sessionId, setCurrentPhase, setUploadStatus]);

    const resetToContractUpload = useCallback(() => {
        setCurrentPhase('contract');
        setUploadStatus(UPLOAD_STATUS.IDLE);
    }, []);

    return {
        uploadStatus,
        sessionId,
        components,
        messages,
        currentPhase,
        handleFileAnalyzed,
        handleSendMessage,
        handleContractAnalyzed,
        resetToContractUpload
    };
};