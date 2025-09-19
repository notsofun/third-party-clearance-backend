import React from 'react';
import { Upload, message } from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import { AnalyzeResponse, SuccessResponse } from '../../services/types';
import { UploadStatus, API_ENDPOINTS, UPLOAD_STATUS } from '../../constants';
import './style.css';

interface Props {
    onFileAnalyzed: (response: AnalyzeResponse) => void;
    onContractAnalyzed: (response: SuccessResponse) => void;
    uploadStatus: UploadStatus;
    phase: 'license' | 'contract';
    className?: string;
    sessionId?: string;
}

const { Dragger } = Upload;

const FileUpload: React.FC<Props> = ({ onContractAnalyzed, onFileAnalyzed, uploadStatus, phase, className = '', sessionId }) => {

    const endpoint = phase === 'license'
        ? API_ENDPOINTS.ANALYZE_LICENSE
        : `${API_ENDPOINTS.ANALYZE_CONTRACT}/${sessionId}`;

    const uploadText = phase === 'license'
        ? 'Click or drag your license file here, Your file should be an HTML'
        : 'Click or drag your contract file here';

    const handleChange = (info: any) => {
        if (info.file.status === 'done') {
            if (info.file.response && info.file.response.session_id) {  // 检查是否有session_id而不是success
                message.success(`${phase} file uploaded and analyzed successfully`);
                console.log('file uploaded and analyzed successfully');
                onFileAnalyzed(info.file.response);
            }
            if (info.file.response.success) {
                console.log('contract analyzed sucessfully');
                onContractAnalyzed(info.file.response);
            }
            else {
                message.error(`Analysis failed: ${info.file.response?.message || 'Unknown response format'}`);
            }
        } else if (info.file.status === 'error') {
            message.error(`${phase} file upload failed: ${info.file.response?.message || 'Unknown error'}`);
        }
    };

    return (
        <div className={`file-upload-container ${className}`}>
            <Dragger
                name="file"
                multiple={false}
                action={endpoint}
                onChange={handleChange}
                disabled={uploadStatus === UPLOAD_STATUS.ANALYZING}
                className="file-upload-dragger"
            >
                <p className="ant-upload-drag-icon">
                    <InboxOutlined />
                </p>
                <p className="ant-upload-text">{uploadText}</p>
                {uploadStatus === UPLOAD_STATUS.ANALYZING && (
                    <p className="ant-upload-hint">Analyzing...</p>
                )}
            </Dragger>
        </div>
    );
};

export default FileUpload;