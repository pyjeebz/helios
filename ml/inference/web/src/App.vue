<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { RouterView, RouterLink, useRoute, useRouter } from 'vue-router'
import {
  Bars3Icon,
  XMarkIcon,
  HomeIcon,
  ServerStackIcon,
  ChartBarIcon,
  ExclamationTriangleIcon,
  Cog6ToothIcon,
  SunIcon,
  MoonIcon,
  PlusIcon,
  CommandLineIcon,
  Square3Stack3DIcon
} from '@heroicons/vue/24/outline'
import { useThemeStore } from '@/stores/theme'
import { useDeploymentsStore } from '@/stores/deployments'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const deploymentsStore = useDeploymentsStore()

const sidebarOpen = ref(false)
const deploymentDropdownOpen = ref(false)

const navigation = [
  { name: 'Dashboard', href: '/', icon: HomeIcon },
  { name: 'Agents', href: '/agents', icon: ServerStackIcon },
  { name: 'Predictions', href: '/predictions', icon: ChartBarIcon },
  { name: 'Anomalies', href: '/anomalies', icon: ExclamationTriangleIcon },
  { name: 'Deployments', href: '/deployments', icon: Square3Stack3DIcon }
]

function isActive(href: string) {
  if (href === '/') return route.path === '/'
  return route.path.startsWith(href)
}

function getEnvironmentBadge(env: string) {
  switch (env) {
    case 'production': return { text: 'prod', class: 'bg-green-500' }
    case 'staging': return { text: 'stg', class: 'bg-yellow-500' }
    case 'development': return { text: 'dev', class: 'bg-blue-500' }
    default: return { text: env, class: 'bg-slate-500' }
  }
}

function selectDeployment(id: string) {
  deploymentsStore.setCurrentDeployment(id)
  deploymentDropdownOpen.value = false
}

function goToInstall() {
  deploymentDropdownOpen.value = false
  router.push('/install')
}

onMounted(() => {
  deploymentsStore.fetchDeployments()
})
</script>

<template>
  <div class="min-h-screen bg-slate-50 dark:bg-slate-950">
    <!-- Mobile sidebar overlay -->
    <div
      v-if="sidebarOpen"
      class="fixed inset-0 z-40 bg-black/50 lg:hidden"
      @click="sidebarOpen = false"
    />

    <!-- Sidebar -->
    <aside
      :class="[
        'fixed inset-y-0 left-0 z-50 w-64 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 transform transition-transform lg:translate-x-0',
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      ]"
    >
      <!-- Logo -->
      <div class="h-16 flex items-center gap-3 px-6 border-b border-slate-200 dark:border-slate-800">
        <div class="w-8 h-8 bg-gradient-to-br from-violet-500 to-blue-500 rounded-lg flex items-center justify-center">
          <span class="text-white font-bold text-sm">H</span>
        </div>
        <span class="text-lg font-semibold text-slate-900 dark:text-white">Helios</span>
      </div>

      <!-- Navigation -->
      <nav class="p-4 space-y-1">
        <RouterLink
          v-for="item in navigation"
          :key="item.name"
          :to="item.href"
          :class="[
            'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
            isActive(item.href)
              ? 'bg-helios-50 dark:bg-helios-900/20 text-helios-600 dark:text-helios-400'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          ]"
          @click="sidebarOpen = false"
        >
          <component :is="item.icon" class="w-5 h-5" />
          {{ item.name }}
        </RouterLink>

        <!-- Install Agent link -->
        <RouterLink
          to="/install"
          class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
          :class="{ 'bg-helios-50 dark:bg-helios-900/20 text-helios-600 dark:text-helios-400': route.path === '/install' }"
          @click="sidebarOpen = false"
        >
          <CommandLineIcon class="w-5 h-5" />
          Install Agent
        </RouterLink>
      </nav>
    </aside>

    <!-- Main content -->
    <div class="lg:pl-64">
      <!-- Top bar -->
      <header class="h-16 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-4 lg:px-6">
        <button
          @click="sidebarOpen = true"
          class="lg:hidden p-2 text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
        >
          <Bars3Icon class="w-6 h-6" />
        </button>

        <div class="flex-1" />

        <!-- Deployment Selector -->
        <div class="relative mr-4" v-if="deploymentsStore.deployments.length > 0">
          <button
            @click="deploymentDropdownOpen = !deploymentDropdownOpen"
            class="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
          >
            <span
              v-if="deploymentsStore.currentDeployment"
              :class="['w-2 h-2 rounded-full', getEnvironmentBadge(deploymentsStore.currentDeployment.environment).class]"
            ></span>
            <span class="text-sm font-medium text-slate-700 dark:text-slate-300">
              {{ deploymentsStore.currentDeployment?.name || 'Select Deployment' }}
            </span>
            <svg class="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          <!-- Dropdown -->
          <div
            v-if="deploymentDropdownOpen"
            class="absolute right-0 mt-1 w-56 bg-white dark:bg-slate-900 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 py-1 z-50"
          >
            <button
              v-for="dep in deploymentsStore.deployments"
              :key="dep.id"
              @click="selectDeployment(dep.id)"
              :class="[
                'w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-slate-50 dark:hover:bg-slate-800',
                deploymentsStore.currentDeploymentId === dep.id ? 'bg-helios-50 dark:bg-helios-900/20' : ''
              ]"
            >
              <span :class="['w-2 h-2 rounded-full', getEnvironmentBadge(dep.environment).class]"></span>
              <span class="text-slate-700 dark:text-slate-300">{{ dep.name }}</span>
            </button>
            <div class="border-t border-slate-200 dark:border-slate-700 my-1"></div>
            <button
              @click="goToInstall"
              class="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-slate-50 dark:hover:bg-slate-800 text-helios-600 dark:text-helios-400"
            >
              <PlusIcon class="w-4 h-4" />
              Add Deployment
            </button>
          </div>
        </div>

        <!-- Theme toggle -->
        <button
          @click="themeStore.toggle()"
          class="p-2 text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
        >
          <SunIcon v-if="themeStore.isDark" class="w-5 h-5" />
          <MoonIcon v-else class="w-5 h-5" />
        </button>
      </header>

      <!-- Click outside to close dropdown -->
      <div v-if="deploymentDropdownOpen" class="fixed inset-0 z-40" @click="deploymentDropdownOpen = false"></div>

      <!-- Page content -->
      <main class="p-4 lg:p-6">
        <RouterView />
      </main>
    </div>
  </div>
</template>

