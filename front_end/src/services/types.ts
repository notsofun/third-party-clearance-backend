export interface Component {
    title: string;
    CheckedLevel: string;
    Justification: string;
    status?: string;
}

export interface AnalyzeResponse {
    session_id: string;
    components: Component[];
}

export interface ChatResponse {
    status: string;
    message?: string | string[]| ComplexMessage;
    download?: {
        available: boolean;
        url: string;
        filename: string;
    };
}

export interface statusResponse {
    status: string;
    components: any;
    current_component_idx : number;
}

export interface AnalyzeResponse {
    session_id: string;
    components: Component[];
    message: string;
    status: string;
}

export interface SuccessResponse {
    success: boolean;
    message: string;
    data?: any;
}

export interface OSSRisks {
    compliance_check?: string;
    discrepancies?: string;
    identified_license?: string;
    mitigation_measures?: string[];
}

export interface ComplexMessage {
    OSS_Risks?: OSSRisks;
    [key: string]: any; // 允许其他可能的字段
}
