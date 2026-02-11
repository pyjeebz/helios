import axios from 'axios'

// API base instance - proxied through vite config
const api = axios.create({
    baseURL: '/api',
    headers: {
        'Content-Type': 'application/json'
    }
})

// Prediction types
export interface PredictionRequest {
    metric: string
    periods: number
    model?: string
    include_confidence?: boolean
}

export interface PredictionPoint {
    timestamp: string
    value: number
    lower_bound?: number
    upper_bound?: number
}

export interface PredictionResponse {
    metric: string
    model: string
    periods: number
    predictions: PredictionPoint[]
    metadata?: Record<string, any>
}

// Anomaly types
export interface DataPoint {
    timestamp: string
    value: number
}

export interface AnomalyRequest {
    metrics: Record<string, DataPoint[]>
    threshold_sigma?: number
}

export interface Anomaly {
    metric: string
    timestamp: string
    value: number
    expected: number
    score: number
    severity: 'low' | 'medium' | 'high' | 'critical'
    description: string
}

export interface AnomalyResponse {
    data_points_analyzed: number
    anomalies_detected: number
    anomalies: Anomaly[]
    summary: Record<string, any>
}

// Recommendation types
export interface RecommendationRequest {
    workload: string
    namespace: string
    current_state: {
        replicas: number
        cpu_request: string
        memory_request: string
        cpu_limit?: string
        memory_limit?: string
    }
    predictions?: PredictionPoint[]
    target_utilization?: number
}

export interface RecommendationAction {
    action: string
    current?: string | number
    recommended?: string | number
    confidence: number
    reason: string
}

export interface Recommendation {
    workload: string
    namespace: string
    priority: string
    actions: RecommendationAction[]
}

export interface RecommendationResponse {
    recommendations: Recommendation[]
}

// Retraining types
export interface TrainingRunInfo {
    started_at: string | null
    completed_at: string | null
    status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
    data_source: string
    data_points: number
    training_hours: number
    metrics: Record<string, any>
    deployed: boolean
    error: string | null
}

export interface RetrainStatus {
    enabled: boolean
    running: boolean
    data_source: string
    interval_hours: number
    training_hours: number
    next_run: string | null
    total_runs: number
    last_run: TrainingRunInfo | null
}

// ML API methods
export const mlApi = {
    predict: (request: PredictionRequest): Promise<PredictionResponse> =>
        api.post('/v1/predict', request).then(res => res.data),

    batchPredict: (metrics: string[], periods: number, model = 'baseline') =>
        api.post('/v1/predict/batch', { metrics, periods, model }).then(res => res.data),

    detect: (request: AnomalyRequest): Promise<AnomalyResponse> =>
        api.post('/v1/detect', request).then(res => res.data),

    recommend: (request: RecommendationRequest): Promise<RecommendationResponse> =>
        api.post('/v1/recommend', request).then(res => res.data),

    // Retraining
    getRetrainStatus: (): Promise<RetrainStatus> =>
        api.get('/retrain/status').then(res => res.data),

    triggerRetrain: (hours?: number): Promise<TrainingRunInfo> =>
        api.post('/retrain/trigger', hours ? { hours } : {}).then(res => res.data),

    getRetrainHistory: (limit = 10): Promise<{ history: TrainingRunInfo[] }> =>
        api.get(`/retrain/history?limit=${limit}`).then(res => res.data),
}

export default api
