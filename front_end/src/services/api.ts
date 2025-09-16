import axios from 'axios';
import { AnalyzeResponse, ChatResponse, statusResponse } from './types';

export const API_BASE = 'http://127.0.0.1:8000';

export const analyzeFile = async (file: File): Promise<AnalyzeResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await axios.post<AnalyzeResponse>(
    `${API_BASE}/analyze`,
    formData,
    {headers: {
        'Content-Type': 'multipart/form-data',
        },
    }
    );
    return response.data;
};

export const sendMessage = async (
    sessionId: string,
    message: string
): Promise<ChatResponse> => {
    const response = await axios.post<ChatResponse>(
    `${API_BASE}/chat/${sessionId}`,
    { message }
    );
    return response.data;
};

export const getSessionStatus = async (
    sessionID:string
) : Promise<statusResponse> => {
    const response = await axios.get<statusResponse>(`${API_BASE}/sessions/${sessionID}`);
    return response.data;
}