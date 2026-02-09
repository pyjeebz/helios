<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import {
  ServerStackIcon,
  ExclamationTriangleIcon,
  LightBulbIcon,
  ChartBarIcon,
  ArrowRightIcon,
  CheckCircleIcon
} from '@heroicons/vue/24/outline'
import { useDeploymentsStore } from '@/stores/deployments'
import { useAgentsStore } from '@/stores/agents'
import { CubeIcon } from '@heroicons/vue/24/outline'
import EmptyState from '@/components/common/EmptyState.vue'
import { mlApi, type Recommendation } from '@/services/api'

const deploymentsStore = useDeploymentsStore()
const agentsStore = useAgentsStore()

// State
const recommendations = ref<Recommendation[]>([])
const anomalyCount = ref(0)
const loadingRecs = ref(false)

// Fetch recommendations (lightweight)
async function fetchRecommendations() {
  if (!deploymentsStore.currentDeployment) return
  loadingRecs.value = true
  try {
    const response = await mlApi.recommend({
      workload: deploymentsStore.currentDeployment.name,
      namespace: 'default',
      current_state: {
        replicas: 2,
        cpu_request: '100m',
        memory_request: '256Mi'
      }
    })
    recommendations.value = response.recommendations || []
  } catch (e) {
    console.error('Failed to fetch recommendations:', e)
  } finally {
    loadingRecs.value = false
  }
}

onMounted(async () => {
  await deploymentsStore.fetchDeployments()
  if (deploymentsStore.currentDeploymentId) {
    await agentsStore.fetchAgents()
    await fetchRecommendations()
  }
})

// Watch for deployment changes
watch(() => deploymentsStore.currentDeploymentId, async (newId) => {
  if (newId) {
    await agentsStore.fetchAgents()
    await fetchRecommendations()
  }
})
</script>

<template>
  <div class="space-y-6">
    <!-- Page Header -->
    <div>
      <h1 class="text-2xl font-semibold text-slate-900 dark:text-white">Dashboard</h1>
      <p class="text-slate-500 dark:text-slate-400">
        AI-powered insights for your infrastructure
      </p>
    </div>
    
    <!-- Empty State if no deployment -->
    <EmptyState
      v-if="!deploymentsStore.currentDeployment"
      title="No deployments yet"
      description="Create your first deployment to start getting AI insights."
      action-label="Create Deployment"
      :icon="CubeIcon"
      @action="$router.push('/deployments')"
    />
    
    <template v-else>
      <!-- Quick Stats -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <!-- Agents Status -->
        <div class="card p-5 flex items-center gap-4">
          <div class="w-12 h-12 rounded-xl bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
            <ServerStackIcon class="w-6 h-6 text-green-600 dark:text-green-400" />
          </div>
          <div>
            <p class="text-2xl font-bold text-slate-900 dark:text-white">
              {{ agentsStore.onlineAgents.length }}
            </p>
            <p class="text-sm text-slate-500">Agents Online</p>
          </div>
        </div>
        
        <!-- Anomalies -->
        <div class="card p-5 flex items-center gap-4">
          <div :class="[
            'w-12 h-12 rounded-xl flex items-center justify-center',
            anomalyCount > 0 
              ? 'bg-red-100 dark:bg-red-900/30' 
              : 'bg-slate-100 dark:bg-slate-800'
          ]">
            <ExclamationTriangleIcon :class="[
              'w-6 h-6',
              anomalyCount > 0 
                ? 'text-red-600 dark:text-red-400' 
                : 'text-slate-400'
            ]" />
          </div>
          <div>
            <p class="text-2xl font-bold text-slate-900 dark:text-white">
              {{ anomalyCount }}
            </p>
            <p class="text-sm text-slate-500">Active Anomalies</p>
          </div>
        </div>
        
        <!-- Recommendations -->
        <div class="card p-5 flex items-center gap-4">
          <div :class="[
            'w-12 h-12 rounded-xl flex items-center justify-center',
            recommendations.length > 0 
              ? 'bg-amber-100 dark:bg-amber-900/30' 
              : 'bg-slate-100 dark:bg-slate-800'
          ]">
            <LightBulbIcon :class="[
              'w-6 h-6',
              recommendations.length > 0 
                ? 'text-amber-600 dark:text-amber-400' 
                : 'text-slate-400'
            ]" />
          </div>
          <div>
            <p class="text-2xl font-bold text-slate-900 dark:text-white">
              {{ recommendations.length }}
            </p>
            <p class="text-sm text-slate-500">Recommendations</p>
          </div>
        </div>
      </div>
      
      <!-- Quick Actions -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <!-- Predictions Card -->
        <RouterLink 
          to="/predictions" 
          class="card p-6 hover:border-helios-500 dark:hover:border-helios-400 transition-all group"
        >
          <div class="flex items-center justify-between mb-4">
            <div class="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
              <ChartBarIcon class="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <ArrowRightIcon class="w-5 h-5 text-slate-400 group-hover:text-helios-500 transition-colors" />
          </div>
          <h3 class="font-semibold text-slate-900 dark:text-white mb-1">Predictions</h3>
          <p class="text-sm text-slate-500">Forecast CPU, memory, and resource usage</p>
        </RouterLink>
        
        <!-- Anomalies Card -->
        <RouterLink 
          to="/anomalies" 
          class="card p-6 hover:border-helios-500 dark:hover:border-helios-400 transition-all group"
        >
          <div class="flex items-center justify-between mb-4">
            <div class="w-10 h-10 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
              <ExclamationTriangleIcon class="w-5 h-5 text-red-600 dark:text-red-400" />
            </div>
            <ArrowRightIcon class="w-5 h-5 text-slate-400 group-hover:text-helios-500 transition-colors" />
          </div>
          <h3 class="font-semibold text-slate-900 dark:text-white mb-1">Anomalies</h3>
          <p class="text-sm text-slate-500">Detect unusual patterns in your metrics</p>
        </RouterLink>
        
        <!-- Agents Card -->
        <RouterLink 
          to="/agents" 
          class="card p-6 hover:border-helios-500 dark:hover:border-helios-400 transition-all group"
        >
          <div class="flex items-center justify-between mb-4">
            <div class="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
              <ServerStackIcon class="w-5 h-5 text-green-600 dark:text-green-400" />
            </div>
            <ArrowRightIcon class="w-5 h-5 text-slate-400 group-hover:text-helios-500 transition-colors" />
          </div>
          <h3 class="font-semibold text-slate-900 dark:text-white mb-1">Agents</h3>
          <p class="text-sm text-slate-500">Manage data collectors across your infrastructure</p>
        </RouterLink>
      </div>
      
      <!-- Recommendations Section -->
      <div class="card p-6">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-medium text-slate-900 dark:text-white">
            AI Recommendations
          </h3>
          <button 
            @click="fetchRecommendations" 
            :disabled="loadingRecs"
            class="text-sm text-helios-600 hover:text-helios-700 disabled:opacity-50"
          >
            {{ loadingRecs ? 'Loading...' : 'Refresh' }}
          </button>
        </div>
        
        <div v-if="recommendations.length > 0" class="space-y-3">
          <div
            v-for="(rec, idx) in recommendations"
            :key="idx"
            class="p-4 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800"
          >
            <div class="flex items-start gap-3">
              <LightBulbIcon class="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div class="flex-1">
                <p class="font-medium text-amber-900 dark:text-amber-100">
                  {{ rec.workload }}
                </p>
                <div v-for="(action, aidx) in rec.actions" :key="aidx" class="mt-2 text-sm text-amber-700 dark:text-amber-300">
                  <p>{{ action.reason }}</p>
                  <p class="text-xs mt-1 text-amber-600">
                    {{ ((action.confidence ?? 0) * 100).toFixed(0) }}% confidence
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div v-else class="flex flex-col items-center py-8 text-center">
          <CheckCircleIcon class="w-12 h-12 text-green-500 mb-3" />
          <p class="font-medium text-slate-900 dark:text-white">All systems optimal</p>
          <p class="text-sm text-slate-500 mt-1">No recommendations at this time</p>
        </div>
      </div>
    </template>
  </div>
</template>
