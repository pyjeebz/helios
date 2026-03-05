import { useState, useEffect, useCallback } from 'react'
import { mlApi, type Agent } from '@/services/api'

export function useAgents(deploymentId: string | null) {
    const [agents, setAgents] = useState<Agent[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const online = agents.filter(a => a.status === 'online')
    const warning = agents.filter(a => a.status === 'warning')
    const offline = agents.filter(a => a.status === 'offline')

    const refresh = useCallback(async () => {
        if (!deploymentId) return
        setLoading(true)
        setError(null)
        try {
            const data = await mlApi.getAgents(deploymentId)
            setAgents(data)
        } catch (e: any) {
            setError(e.message || 'Failed to fetch agents')
        } finally {
            setLoading(false)
        }
    }, [deploymentId])

    useEffect(() => { refresh() }, [refresh])

    return { agents, online, warning, offline, loading, error, refresh }
}
