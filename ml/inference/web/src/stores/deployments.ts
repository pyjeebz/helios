import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'

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

export const useDeploymentsStore = defineStore('deployments', () => {
    const deployments = ref<Deployment[]>([])
    const currentDeploymentId = ref<string | null>(null)
    const loading = ref(false)
    const error = ref<string | null>(null)

    const currentDeployment = computed(() =>
        deployments.value.find(d => d.id === currentDeploymentId.value) || null
    )

    async function fetchDeployments() {
        loading.value = true
        error.value = null
        try {
            const response = await api.get('/deployments')
            deployments.value = response.data
            // Auto-select first deployment if none selected
            if (!currentDeploymentId.value && deployments.value.length > 0) {
                currentDeploymentId.value = deployments.value[0].id
            }
        } catch (e: any) {
            error.value = e.message || 'Failed to fetch deployments'
            console.error('Failed to fetch deployments:', e)
        } finally {
            loading.value = false
        }
    }

    async function createDeployment(data: { name: string; description?: string; environment?: string }) {
        loading.value = true
        try {
            const response = await api.post('/deployments', data)
            deployments.value.push(response.data)
            return response.data
        } catch (e: any) {
            error.value = e.message || 'Failed to create deployment'
            throw e
        } finally {
            loading.value = false
        }
    }

    function setCurrentDeployment(id: string) {
        currentDeploymentId.value = id
    }

    return {
        deployments,
        currentDeploymentId,
        currentDeployment,
        loading,
        error,
        fetchDeployments,
        createDeployment,
        setCurrentDeployment
    }
})
