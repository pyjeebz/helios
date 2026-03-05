import axios from 'axios'

const api = axios.create({
    baseURL: '/api',
    headers: { 'Content-Type': 'application/json' }
})

/* ─── Types ─── */
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

export interface Deployment {
    id: string
    name: string
    description: string
    environment: 'development' | 'staging' | 'production'
    created_at: string
    updated_at: string
    agents_count: number
    agents_online: number
    metrics_count: number
}

export interface Agent {
    id: string
    deployment_id: string
    hostname: string
    platform: string
    agent_version: string
    status: 'online' | 'warning' | 'offline'
    last_seen: string
    paused: boolean
    collection_interval: number
    metrics: string[]
    metrics_count: number
}

/* ─── API methods ─── */
export const mlApi = {
    predict: (metric: string, periods: number, model = 'baseline'): Promise<PredictionResponse> =>
        api.post('/v1/predict', { metric, periods, model, include_confidence: true }).then(r => r.data),

    detect: (metrics: Record<string, { timestamp: string; value: number }[]>): Promise<AnomalyResponse> =>
        api.post('/v1/detect', { metrics }).then(r => r.data),

    recommend: (workload: string, namespace: string, replicas: number): Promise<{ recommendations: Recommendation[] }> =>
        api.post('/v1/recommend', {
            workload, namespace,
            current_state: { replicas, cpu_request: '100m', memory_request: '256Mi' }
        }).then(r => r.data),

    getRetrainStatus: (): Promise<RetrainStatus> =>
        api.get('/retrain/status').then(r => r.data),

    triggerRetrain: (hours = 24): Promise<TrainingRunInfo> =>
        api.post('/retrain/trigger', { hours }).then(r => r.data),

    getDeployments: (): Promise<Deployment[]> =>
        api.get('/deployments').then(r => r.data),

    createDeployment: (data: { name: string; description?: string; environment?: string }): Promise<Deployment> =>
        api.post('/deployments', data).then(r => r.data),

    deleteDeployment: (id: string): Promise<void> =>
        api.delete(`/deployments/${id}`).then(r => r.data),

    getAgents: (deploymentId: string): Promise<Agent[]> =>
        api.get(`/deployments/${deploymentId}/agents`).then(r => r.data),

    deleteAgent: (agentId: string): Promise<void> =>
        api.delete(`/agents/${agentId}`).then(r => r.data),
}

export default api
