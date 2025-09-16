import React from 'react';
// import { message } from 'antd';
import FileUpload from '../../components/FileUpload';
import ComponentList from '../../components/ComponentList';
import ChatWindow from '../../components/ChatWindow';
import { useReviewPage } from './hooks/useReviewPage';
import { UPLOAD_STATUS } from '../../constants';
import './style.css';

const ReviewPage: React.FC = () => {
    const {
        uploadStatus,
        sessionId,
        components,
        messages,
        currentPhase,
        handleFileAnalyzed,
        handleContractAnalyzed,
        handleSendMessage
    } = useReviewPage();

    // 如果uploadStatus和UPLOAD_STATUS.IDLE相等，就赋值True给ShowFileUpload
    const showFileUpload = (uploadStatus === UPLOAD_STATUS.IDLE) || (uploadStatus === UPLOAD_STATUS.CONTRACT);
    const showContent = (uploadStatus === UPLOAD_STATUS.ANALYZED || uploadStatus === UPLOAD_STATUS.CONTRACT) && sessionId;
    console.log('now we need to show content?', showContent)
    console.log('now the upload status is', uploadStatus)
    // console.log('we have messages like', messages)

    return (
        <div className="review-page">
            {showFileUpload && (
                <FileUpload
                    onFileAnalyzed={handleFileAnalyzed}
                    onContractAnalyzed={handleContractAnalyzed}
                    uploadStatus={uploadStatus}
                    phase={currentPhase}
                    className={!sessionId ? 'centered-upload' : ''}
                    sessionId= {sessionId}
                />
            )}

            {showContent && (
                <div className="content-area">
                    <ComponentList components={components} />
                    <ChatWindow
                        messages={messages}
                        onSendMessage={handleSendMessage}
                    />
                </div>
            )}
        </div>
    );
};

export default ReviewPage;