import { Server, RefreshCw, Pause, Play, Trash2 } from 'lucide-react'
import { useDeployments } from '@/context/DeploymentsContext'
import { useAgents } from '@/hooks/useAgents'

export function AgentsView() {
    const { currentId, current } = useDeployments()
    const { agents, online, warning, offline, loading, refresh } = useAgents(currentId)

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>Agents</h1>
                    <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                        {online.length} online · {warning.length} warning · {offline.length} offline
                    </p>
                </div>
                <button
                    onClick={refresh}
                    disabled={loading}
                    className="flex items-center gap-2 px-3 py-2 text-sm rounded-lg cursor-pointer"
                    style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
                >
                    <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    Refresh
                </button>
            </div>

            {agents.length === 0 ? (
                <div className="bento-card p-12 text-center">
                    <Server className="w-12 h-12 mx-auto mb-3" style={{ color: 'var(--text-faint)' }} />
                    <p className="font-medium mb-1" style={{ color: 'var(--text-primary)' }}>No agents found</p>
                    <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                        Install the PreScale agent to start collecting metrics
                    </p>
                </div>
            ) : (
                <div className="grid gap-3">
                    {agents.map(agent => (
                        <div key={agent.id} className="bento-card p-4 flex items-center gap-4">
                            <div className={`w-2.5 h-2.5 rounded-full ${agent.status === 'online' ? 'bg-emerald-400' : agent.status === 'warning' ? 'bg-amber-400' : 'bg-red-400'}`} />
                            <div className="flex-1 min-w-0">
                                <div className="font-medium text-sm truncate" style={{ color: 'var(--text-primary)' }}>{agent.hostname}</div>
                                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                                    {agent.platform} · v{agent.agent_version} · {agent.metrics_count} metrics
                                </div>
                            </div>
                            <span className="text-xs font-mono px-2 py-1 rounded" style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>
                                {agent.collection_interval}s
                            </span>
                            <span className={`text-xs px-2 py-1 rounded-full font-medium ${agent.status === 'online' ? 'bg-emerald-500/10 text-emerald-400' :
                                    agent.status === 'warning' ? 'bg-amber-500/10 text-amber-400' :
                                        'bg-red-500/10 text-red-400'
                                }`}>
                                {agent.status}
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
