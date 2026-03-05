import { BarChart3 } from 'lucide-react'

export function PredictionsView() {
    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>Predictions</h1>
                <p style={{ color: 'var(--text-muted)' }}>Forecast CPU, memory, and resource usage</p>
            </div>
            <div className="bento-card p-12 text-center">
                <BarChart3 className="w-12 h-12 mx-auto mb-3" style={{ color: 'var(--text-faint)' }} />
                <p className="font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Prediction charts coming soon</p>
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                    View forecasts for CPU, memory, and custom metrics
                </p>
            </div>
        </div>
    )
}
