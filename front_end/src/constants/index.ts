export const UPLOAD_STATUS = {
    IDLE: 'idle',
    ANALYZING: 'analyzing',
    ANALYZED: 'analyzed',
    CONTRACT: 'contract'
} as const;

export const CHAT_STATUS = {
    CONTINUE: 'continue',
    COMPLETED: 'completed',
    TO_CONTRACT: 'toContract'
} as const;

export const API_ENDPOINTS = {
    ANALYZE_LICENSE: 'http://127.0.0.1:8000/analyze',
    ANALYZE_CONTRACT: 'http://127.0.0.1:8000/analyze-contract'
} as const;

export type UploadStatus = typeof UPLOAD_STATUS[keyof typeof UPLOAD_STATUS];
export type ChatStatus = typeof CHAT_STATUS[keyof typeof CHAT_STATUS];