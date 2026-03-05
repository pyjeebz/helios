import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { mlApi, type Deployment } from '@/services/api'

interface DeploymentsContextValue {
    deployments: Deployment[]
    current: Deployment | null
    currentId: string | null
    loading: boolean
    error: string | null
    setCurrent: (id: string) => void
    refresh: () => Promise<void>
    create: (data: { name: string; description?: string; environment?: string }) => Promise<Deployment>
    remove: (id: string) => Promise<void>
}

const DeploymentsContext = createContext<DeploymentsContextValue>({
    deployments: [],
    current: null,
    currentId: null,
    loading: false,
    error: null,
    setCurrent: () => { },
    refresh: async () => { },
    create: async () => ({} as Deployment),
    remove: async () => { },
})

export function DeploymentsProvider({ children }: { children: ReactNode }) {
    const [deployments, setDeployments] = useState<Deployment[]>([])
    const [currentId, setCurrentId] = useState<string | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const current = deployments.find(d => d.id === currentId) || null

    const refresh = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            const data = await mlApi.getDeployments()
            setDeployments(data)
            if (!currentId && data.length > 0) setCurrentId(data[0].id)
        } catch (e: any) {
            setError(e.message || 'Failed to fetch deployments')
        } finally {
            setLoading(false)
        }
    }, [currentId])

    const create = useCallback(async (data: { name: string; description?: string; environment?: string }) => {
        const dep = await mlApi.createDeployment(data)
        setDeployments(prev => [...prev, dep])
        return dep
    }, [])

    const remove = useCallback(async (id: string) => {
        await mlApi.deleteDeployment(id)
        setDeployments(prev => prev.filter(d => d.id !== id))
        if (currentId === id) {
            setCurrentId(deployments.length > 1 ? deployments.find(d => d.id !== id)?.id || null : null)
        }
    }, [currentId, deployments])

    useEffect(() => { refresh() }, [])

    return (
        <DeploymentsContext.Provider value={{
            deployments, current, currentId, loading, error,
            setCurrent: setCurrentId, refresh, create, remove,
        }}>
            {children}
        </DeploymentsContext.Provider>
    )
}

export const useDeployments = () => useContext(DeploymentsContext)
