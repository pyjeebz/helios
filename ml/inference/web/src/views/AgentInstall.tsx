import { Terminal, Copy, Check } from 'lucide-react'
import { useState } from 'react'

function CopyBlock({ code, language = 'bash' }: { code: string; language?: string }) {
    const [copied, setCopied] = useState(false)

    function copy() {
        navigator.clipboard.writeText(code)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
    }

    return (
        <div className="relative rounded-lg overflow-hidden" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
            <button
                onClick={copy}
                className="absolute top-2 right-2 p-1.5 rounded cursor-pointer transition-colors"
                style={{ color: 'var(--text-muted)' }}
            >
                {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            </button>
            <pre className="p-4 text-sm font-mono overflow-x-auto" style={{ color: 'var(--text-secondary)' }}>
                <code>{code}</code>
            </pre>
        </div>
    )
}

export function AgentInstallView() {
    return (
        <div className="space-y-6 max-w-2xl">
            <div>
                <h1 className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>Install Agent</h1>
                <p style={{ color: 'var(--text-muted)' }}>Deploy the PreScale agent to start collecting metrics</p>
            </div>

            <div className="bento-card p-6 space-y-4">
                <div className="flex items-center gap-2">
                    <Terminal className="w-5 h-5 text-indigo-400" />
                    <h2 className="font-medium" style={{ color: 'var(--text-primary)' }}>Quick Install (pip)</h2>
                </div>
                <CopyBlock code="pip install prescale-agent" />
            </div>

            <div className="bento-card p-6 space-y-4">
                <h2 className="font-medium" style={{ color: 'var(--text-primary)' }}>Kubernetes (Helm)</h2>
                <CopyBlock code={`helm repo add prescale https://pyjeebz.github.io/prescale
helm install prescale prescale/prescale`} />
            </div>

            <div className="bento-card p-6 space-y-4">
                <h2 className="font-medium" style={{ color: 'var(--text-primary)' }}>Docker</h2>
                <CopyBlock code={`docker pull ghcr.io/pyjeebz/prescale/inference:latest
docker pull ghcr.io/pyjeebz/prescale/cost-intelligence:latest`} />
            </div>

            <div className="bento-card p-6 space-y-4">
                <h2 className="font-medium" style={{ color: 'var(--text-primary)' }}>Configuration</h2>
                <CopyBlock language="yaml" code={`# prescale-agent.yaml
api_url: http://localhost:8001
collection_interval: 30
metrics:
  - cpu_usage
  - memory_usage
  - network_io
  - disk_usage`} />
            </div>
        </div>
    )
}
