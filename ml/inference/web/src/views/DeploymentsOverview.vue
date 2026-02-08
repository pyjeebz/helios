<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useDeploymentsStore, type Deployment } from '@/stores/deployments'
import { PlusIcon, ServerStackIcon, ExclamationTriangleIcon, CheckCircleIcon } from '@heroicons/vue/24/outline'

const deploymentsStore = useDeploymentsStore()

const showCreateModal = ref(false)
const newDeployment = ref({
  name: '',
  description: '',
  environment: 'production' as 'development' | 'staging' | 'production'
})
const creating = ref(false)

function getEnvironmentColor(env: string) {
  switch (env) {
    case 'production': return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
    case 'staging': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
    case 'development': return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400'
    default: return 'bg-slate-100 text-slate-800 dark:bg-slate-700 dark:text-slate-300'
  }
}

function getHealthStatus(dep: Deployment) {
  const ratio = dep.agents_online / Math.max(dep.agents_count, 1)
  if (ratio >= 0.9) return { label: 'Excellent', color: 'text-green-600 dark:text-green-400' }
  if (ratio >= 0.5) return { label: 'Good', color: 'text-yellow-600 dark:text-yellow-400' }
  return { label: 'Degraded', color: 'text-red-600 dark:text-red-400' }
}

async function createDeployment() {
  if (!newDeployment.value.name.trim()) return
  
  creating.value = true
  try {
    await deploymentsStore.createDeployment({
      name: newDeployment.value.name.trim(),
      description: newDeployment.value.description.trim(),
      environment: newDeployment.value.environment
    })
    showCreateModal.value = false
    newDeployment.value = { name: '', description: '', environment: 'production' }
  } catch (e) {
    console.error('Failed to create deployment:', e)
  } finally {
    creating.value = false
  }
}

function selectDeployment(dep: Deployment) {
  deploymentsStore.setCurrentDeployment(dep.id)
}

onMounted(() => {
  deploymentsStore.fetchDeployments()
})
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-900 dark:text-white">Deployments</h1>
        <p class="text-slate-600 dark:text-slate-400 mt-1">Manage your monitored environments</p>
      </div>
      <button @click="showCreateModal = true" class="btn btn-primary">
        <PlusIcon class="w-5 h-5 mr-2" />
        Add Deployment
      </button>
    </div>

    <!-- Deployments Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div
        v-for="dep in deploymentsStore.deployments"
        :key="dep.id"
        class="card hover:border-helios-500 dark:hover:border-helios-400 transition-colors cursor-pointer"
        :class="{ 'ring-2 ring-helios-500': deploymentsStore.currentDeploymentId === dep.id }"
        @click="selectDeployment(dep)"
      >
        <!-- Header -->
        <div class="flex items-start justify-between mb-4">
          <div class="flex items-center gap-3">
            <div :class="[
              'w-3 h-3 rounded-full',
              dep.agents_online > 0 ? 'bg-green-500' : 'bg-slate-400'
            ]"></div>
            <h3 class="font-semibold text-slate-900 dark:text-white">{{ dep.name }}</h3>
          </div>
          <span :class="['px-2 py-0.5 rounded text-xs font-medium', getEnvironmentColor(dep.environment)]">
            {{ dep.environment }}
          </span>
        </div>

        <!-- Stats -->
        <div class="grid grid-cols-3 gap-4 mb-4">
          <div>
            <div class="text-2xl font-bold text-slate-900 dark:text-white">{{ dep.agents_online }}</div>
            <div class="text-xs text-slate-500 dark:text-slate-400">Agents Online</div>
          </div>
          <div>
            <div class="text-2xl font-bold text-slate-900 dark:text-white">0</div>
            <div class="text-xs text-slate-500 dark:text-slate-400">Anomalies</div>
          </div>
          <div>
            <div :class="['text-sm font-medium', getHealthStatus(dep).color]">
              {{ getHealthStatus(dep).label }}
            </div>
            <div class="text-xs text-slate-500 dark:text-slate-400">Health</div>
          </div>
        </div>

        <!-- Actions -->
        <div class="pt-4 border-t border-slate-200 dark:border-slate-700">
          <RouterLink
            :to="{ path: '/', query: { deployment: dep.id } }"
            class="text-sm text-helios-600 dark:text-helios-400 hover:underline"
            @click.stop
          >
            View Dashboard →
          </RouterLink>
        </div>
      </div>

      <!-- Empty state -->
      <div
        v-if="deploymentsStore.deployments.length === 0 && !deploymentsStore.loading"
        class="col-span-full flex flex-col items-center justify-center py-12 text-center"
      >
        <ServerStackIcon class="w-12 h-12 text-slate-400 mb-4" />
        <h3 class="text-lg font-medium text-slate-900 dark:text-white mb-2">No deployments yet</h3>
        <p class="text-slate-600 dark:text-slate-400 mb-4">Create your first deployment to start monitoring.</p>
        <button @click="showCreateModal = true" class="btn btn-primary">
          <PlusIcon class="w-5 h-5 mr-2" />
          Create Deployment
        </button>
      </div>
    </div>

    <!-- Create Modal -->
    <Teleport to="body">
      <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="fixed inset-0 bg-black/50" @click="showCreateModal = false"></div>
        <div class="relative bg-white dark:bg-slate-900 rounded-xl shadow-xl p-6 w-full max-w-md m-4">
          <h2 class="text-xl font-bold text-slate-900 dark:text-white mb-4">Create Deployment</h2>
          
          <form @submit.prevent="createDeployment" class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                Deployment Name
              </label>
              <input
                v-model="newDeployment.name"
                type="text"
                placeholder="e.g., ecommerce-prod"
                class="input w-full"
                required
              />
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                Description (optional)
              </label>
              <input
                v-model="newDeployment.description"
                type="text"
                placeholder="Production e-commerce platform on GKE"
                class="input w-full"
              />
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                Environment
              </label>
              <div class="flex gap-4">
                <label class="flex items-center gap-2 cursor-pointer">
                  <input v-model="newDeployment.environment" type="radio" value="development" class="text-helios-600" />
                  <span class="text-sm text-slate-700 dark:text-slate-300">Development</span>
                </label>
                <label class="flex items-center gap-2 cursor-pointer">
                  <input v-model="newDeployment.environment" type="radio" value="staging" class="text-helios-600" />
                  <span class="text-sm text-slate-700 dark:text-slate-300">Staging</span>
                </label>
                <label class="flex items-center gap-2 cursor-pointer">
                  <input v-model="newDeployment.environment" type="radio" value="production" class="text-helios-600" />
                  <span class="text-sm text-slate-700 dark:text-slate-300">Production</span>
                </label>
              </div>
            </div>

            <div class="flex justify-end gap-3 pt-4">
              <button type="button" @click="showCreateModal = false" class="btn btn-secondary">
                Cancel
              </button>
              <button type="submit" class="btn btn-primary" :disabled="creating">
                {{ creating ? 'Creating...' : 'Create Deployment' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>
  </div>
</template>
