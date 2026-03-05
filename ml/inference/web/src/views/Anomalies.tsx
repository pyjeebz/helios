import { AlertTriangle } from 'lucide-react'

export function AnomaliesView() {
    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>Anomalies</h1>
                <p style={{ color: 'var(--text-muted)' }}>Detect unusual patterns in your metrics</p>
            </div>
            <div className="bento-card p-12 text-center">
                <AlertTriangle className="w-12 h-12 mx-auto mb-3" style={{ color: 'var(--text-faint)' }} />
                <p className="font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Anomaly detection view coming soon</p>
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                    Real-time anomaly detection with severity classification
                </p>
            </div>
        </div>
    )
}
