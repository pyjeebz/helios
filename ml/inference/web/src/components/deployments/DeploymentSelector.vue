<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Menu, MenuButton, MenuItems, MenuItem } from '@headlessui/vue'
import { ChevronDownIcon, CheckIcon, PlusIcon } from '@heroicons/vue/24/outline'
import { CubeIcon } from '@heroicons/vue/24/solid'
import { useDeploymentsStore } from '@/stores/deployments'

const deploymentsStore = useDeploymentsStore()

const environmentColors = {
  development: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  staging: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  production: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
}

onMounted(() => {
  deploymentsStore.fetchDeployments()
})
</script>

<template>
  <Menu as="div" class="relative">
    <MenuButton class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
      <CubeIcon class="w-5 h-5 text-helios-500" />
      <span class="text-sm font-medium text-slate-700 dark:text-slate-200">
        {{ deploymentsStore.currentDeployment?.name || 'Select Deployment' }}
      </span>
      <ChevronDownIcon class="w-4 h-4 text-slate-400" />
    </MenuButton>
    
    <transition
      enter-active-class="transition duration-100 ease-out"
      enter-from-class="transform scale-95 opacity-0"
      enter-to-class="transform scale-100 opacity-100"
      leave-active-class="transition duration-75 ease-in"
      leave-from-class="transform scale-100 opacity-100"
      leave-to-class="transform scale-95 opacity-0"
    >
      <MenuItems class="absolute right-0 mt-2 w-64 origin-top-right bg-white dark:bg-slate-800 rounded-xl shadow-lg ring-1 ring-black/5 dark:ring-white/10 focus:outline-none z-50">
        <div class="p-2">
          <div class="px-3 py-2 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            Deployments
          </div>
          
          <MenuItem
            v-for="deployment in deploymentsStore.deployments"
            :key="deployment.id"
            v-slot="{ active }"
          >
            <button
              @click="deploymentsStore.setCurrentDeployment(deployment.id)"
              :class="[
                'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left',
                active ? 'bg-slate-100 dark:bg-slate-700' : '',
                deployment.id === deploymentsStore.currentDeploymentId ? 'bg-helios-50 dark:bg-helios-900/20' : ''
              ]"
            >
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium text-slate-900 dark:text-white truncate">
                    {{ deployment.name }}
                  </span>
                  <span :class="['text-xs px-1.5 py-0.5 rounded', environmentColors[deployment.environment]]">
                    {{ deployment.environment }}
                  </span>
                </div>
                <div class="text-xs text-slate-500 dark:text-slate-400">
                  {{ deployment.agents_online }} / {{ deployment.agents_count }} agents online
                </div>
              </div>
              <CheckIcon
                v-if="deployment.id === deploymentsStore.currentDeploymentId"
                class="w-4 h-4 text-helios-500"
              />
            </button>
          </MenuItem>
          
          <div class="border-t border-slate-200 dark:border-slate-700 mt-2 pt-2">
            <MenuItem v-slot="{ active }">
              <router-link
                to="/deployments"
                :class="[
                  'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm',
                  active ? 'bg-slate-100 dark:bg-slate-700' : ''
                ]"
              >
                <PlusIcon class="w-4 h-4 text-slate-500" />
                <span class="text-slate-600 dark:text-slate-300">Create Deployment</span>
              </router-link>
            </MenuItem>
          </div>
        </div>
      </MenuItems>
    </transition>
  </Menu>
</template>
