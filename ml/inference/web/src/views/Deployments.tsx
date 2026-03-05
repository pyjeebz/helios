import { useState } from 'react'
import { Layers, Plus, Trash2 } from 'lucide-react'
import { useDeployments } from '@/context/DeploymentsContext'

export function DeploymentsView() {
    const { deployments, current, setCurrent, create, remove, loading } = useDeployments()
    const [showCreate, setShowCreate] = useState(false)
    const [name, setName] = useState('')
    const [env, setEnv] = useState('production')

    async function handleCreate(e: React.FormEvent) {
        e.preventDefault()
        if (!name.trim()) return
        await create({ name: name.trim(), environment: env })
        setName('')
        setShowCreate(false)
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>Deployments</h1>
                    <p style={{ color: 'var(--text-muted)' }}>{deployments.length} deployment{deployments.length !== 1 ? 's' : ''}</p>
                </div>
                <button
                    onClick={() => setShowCreate(v => !v)}
                    className="flex items-center gap-2 px-3 py-2 text-sm rounded-lg cursor-pointer"
                    style={{ background: 'var(--accent-gradient)', color: 'white' }}
                >
                    <Plus className="w-4 h-4" />
                    New Deployment
                </button>
            </div>

            {showCreate && (
                <form onSubmit={handleCreate} className="bento-card p-4 flex items-end gap-3">
                    <div className="flex-1">
                        <label className="block text-xs mb-1" style={{ color: 'var(--text-muted)' }}>Name</label>
                        <input
                            value={name}
                            onChange={e => setName(e.target.value)}
                            placeholder="my-app-prod"
                            className="w-full px-3 py-2 text-sm rounded-lg"
                            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                        />
                    </div>
                    <div>
                        <label className="block text-xs mb-1" style={{ color: 'var(--text-muted)' }}>Environment</label>
                        <select
                            value={env}
                            onChange={e => setEnv(e.target.value)}
                            className="px-3 py-2 text-sm rounded-lg cursor-pointer"
                            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
                        >
                            <option value="production">Production</option>
                            <option value="staging">Staging</option>
                            <option value="development">Development</option>
                        </select>
                    </div>
                    <button
                        type="submit"
                        className="px-4 py-2 text-sm rounded-lg cursor-pointer"
                        style={{ background: 'var(--accent-gradient)', color: 'white' }}
                    >
                        Create
                    </button>
                </form>
            )}

            {deployments.length === 0 ? (
                <div className="bento-card p-12 text-center">
                    <Layers className="w-12 h-12 mx-auto mb-3" style={{ color: 'var(--text-faint)' }} />
                    <p className="font-medium mb-1" style={{ color: 'var(--text-primary)' }}>No deployments yet</p>
                    <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Create one to get started</p>
                </div>
            ) : (
                <div className="grid gap-3">
                    {deployments.map(dep => {
                        const badge = { production: 'bg-green-500', staging: 'bg-yellow-500', development: 'bg-blue-500' }[dep.environment] || 'bg-slate-500'
                        return (
                            <div
                                key={dep.id}
                                className={`bento-card p-4 flex items-center gap-4 cursor-pointer ${current?.id === dep.id ? 'ring-1 ring-indigo-500/30' : ''}`}
                                onClick={() => setCurrent(dep.id)}
                            >
                                <div className={`w-3 h-3 rounded-full ${badge}`} />
                                <div className="flex-1 min-w-0">
                                    <div className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>{dep.name}</div>
                                    <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                                        {dep.agents_online}/{dep.agents_count} agents · {dep.metrics_count} metrics
                                    </div>
                                </div>
                                <span className="text-xs capitalize px-2 py-1 rounded-full" style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>
                                    {dep.environment}
                                </span>
                                <button
                                    onClick={e => { e.stopPropagation(); if (confirm(`Delete ${dep.name}?`)) remove(dep.id) }}
                                    className="p-1.5 rounded opacity-0 group-hover:opacity-100 hover:text-red-500 transition-opacity cursor-pointer"
                                    style={{ color: 'var(--text-muted)' }}
                                >
                                    <Trash2 className="w-4 h-4" />
                                </button>
                            </div>
                        )
                    })}
                </div>
            )}
        </div>
    )
}
