import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'
import { useDeploymentsStore } from './deployments'

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
    location?: string
    region?: string
    ip_address?: string
}

export const useAgentsStore = defineStore('agents', () => {
    const agents = ref<Agent[]>([])
    const loading = ref(false)
    const error = ref<string | null>(null)

    const deploymentsStore = useDeploymentsStore()

    const currentDeploymentAgents = computed(() =>
        agents.value.filter(a => a.deployment_id === deploymentsStore.currentDeploymentId)
    )

    const onlineAgents = computed(() =>
        currentDeploymentAgents.value.filter(a => a.status === 'online')
    )

    const warningAgents = computed(() =>
        currentDeploymentAgents.value.filter(a => a.status === 'warning')
    )

    const offlineAgents = computed(() =>
        currentDeploymentAgents.value.filter(a => a.status === 'offline')
    )

    async function fetchAgents() {
        if (!deploymentsStore.currentDeploymentId) return

        loading.value = true
        error.value = null
        try {
            const response = await api.get(`/deployments/${deploymentsStore.currentDeploymentId}/agents`)
            agents.value = response.data
        } catch (e: any) {
            error.value = e.message || 'Failed to fetch agents'
            console.error('Failed to fetch agents:', e)
        } finally {
            loading.value = false
        }
    }

    async function deleteAgent(agentId: string) {
        try {
            await api.delete(`/agents/${agentId}`)
            agents.value = agents.value.filter(a => a.id !== agentId)
        } catch (e: any) {
            error.value = e.message || 'Failed to delete agent'
            throw e
        }
    }

    async function updateAgentConfig(agentId: string, config: { paused?: boolean; collection_interval?: number }) {
        try {
            const response = await api.patch(`/agents/${agentId}/config`, config)
            const idx = agents.value.findIndex(a => a.id === agentId)
            if (idx !== -1) {
                agents.value[idx] = response.data
            }
            return response.data
        } catch (e: any) {
            error.value = e.message || 'Failed to update agent config'
            throw e
        }
    }

    return {
        agents,
        currentDeploymentAgents,
        onlineAgents,
        warningAgents,
        offlineAgents,
        loading,
        error,
        fetchAgents,
        deleteAgent,
        updateAgentConfig
    }
})
