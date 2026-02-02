<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import {
  HomeIcon,
  ChartBarIcon,
  ExclamationTriangleIcon,
  LightBulbIcon,
  ServerStackIcon,
  CubeIcon,
  Cog6ToothIcon
} from '@heroicons/vue/24/outline'

const route = useRoute()

const navigation = [
  { name: 'Dashboard', href: '/', icon: HomeIcon },
  { name: 'Predictions', href: '/predictions', icon: ChartBarIcon },
  { name: 'Anomalies', href: '/anomalies', icon: ExclamationTriangleIcon },
  { name: 'Agents', href: '/agents', icon: ServerStackIcon },
  { name: 'Deployments', href: '/deployments', icon: CubeIcon },
]

const bottomNavigation = [
  { name: 'Settings', href: '/settings', icon: Cog6ToothIcon },
]

function isActive(href: string) {
  if (href === '/') {
    return route.path === '/'
  }
  return route.path.startsWith(href)
}
</script>

<template>
  <aside class="w-64 bg-white dark:bg-slate-800 border-r border-slate-200 dark:border-slate-700 flex flex-col">
    <!-- Logo -->
    <div class="h-16 flex items-center px-6 border-b border-slate-200 dark:border-slate-700">
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 bg-gradient-to-br from-helios-500 to-helios-600 rounded-lg flex items-center justify-center">
          <span class="text-white font-bold text-sm">H</span>
        </div>
        <div>
          <h1 class="text-lg font-semibold text-slate-900 dark:text-white">Helios</h1>
          <p class="text-xs text-slate-500 dark:text-slate-400">Infrastructure Forecasting</p>
        </div>
      </div>
    </div>
    
    <!-- Navigation -->
    <nav class="flex-1 px-4 py-4 space-y-1">
      <RouterLink
        v-for="item in navigation"
        :key="item.name"
        :to="item.href"
        :class="isActive(item.href) ? 'sidebar-link-active' : 'sidebar-link'"
      >
        <component :is="item.icon" class="w-5 h-5" />
        <span>{{ item.name }}</span>
      </RouterLink>
    </nav>
    
    <!-- Bottom Navigation -->
    <div class="px-4 py-4 border-t border-slate-200 dark:border-slate-700">
      <RouterLink
        v-for="item in bottomNavigation"
        :key="item.name"
        :to="item.href"
        :class="isActive(item.href) ? 'sidebar-link-active' : 'sidebar-link'"
      >
        <component :is="item.icon" class="w-5 h-5" />
        <span>{{ item.name }}</span>
      </RouterLink>
    </div>
  </aside>
</template>
