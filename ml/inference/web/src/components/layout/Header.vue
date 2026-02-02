<script setup lang="ts">
import { ref } from 'vue'
import { MagnifyingGlassIcon, SunIcon, MoonIcon } from '@heroicons/vue/24/outline'
import { useThemeStore } from '@/stores/theme'
import { useDeploymentsStore } from '@/stores/deployments'
import DeploymentSelector from '@/components/deployments/DeploymentSelector.vue'

const themeStore = useThemeStore()
const deploymentsStore = useDeploymentsStore()

const searchQuery = ref('')
</script>

<template>
  <header class="h-16 bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between px-6">
    <!-- Search -->
    <div class="flex items-center gap-4 flex-1">
      <div class="relative max-w-md w-full">
        <MagnifyingGlassIcon class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search..."
          class="w-full pl-10 pr-4 py-2 bg-slate-100 dark:bg-slate-700 border-0 rounded-lg text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:ring-2 focus:ring-helios-500 outline-none"
        />
      </div>
    </div>
    
    <!-- Right side -->
    <div class="flex items-center gap-4">
      <!-- Deployment Selector -->
      <DeploymentSelector />
      
      <!-- Theme Toggle -->
      <button
        @click="themeStore.toggle()"
        class="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
        :title="themeStore.isDark ? 'Switch to light mode' : 'Switch to dark mode'"
      >
        <SunIcon v-if="themeStore.isDark" class="w-5 h-5 text-yellow-400" />
        <MoonIcon v-else class="w-5 h-5 text-slate-600" />
      </button>
    </div>
  </header>
</template>
