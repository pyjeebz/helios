<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{
  title: string
  value: string | number
  subtitle?: string
  icon?: Component
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'slate'
}>()
</script>

<template>
  <div class="card p-6">
    <div class="flex items-center gap-4">
      <div
        :class="[
          'w-12 h-12 rounded-lg flex items-center justify-center',
          {
            'bg-blue-100 dark:bg-blue-900/30': color === 'blue' || !color,
            'bg-green-100 dark:bg-green-900/30': color === 'green',
            'bg-yellow-100 dark:bg-yellow-900/30': color === 'yellow',
            'bg-red-100 dark:bg-red-900/30': color === 'red',
            'bg-slate-100 dark:bg-slate-700': color === 'slate'
          }
        ]"
      >
        <component
          v-if="icon"
          :is="icon"
          :class="[
            'w-6 h-6',
            {
              'text-blue-600 dark:text-blue-400': color === 'blue' || !color,
              'text-green-600 dark:text-green-400': color === 'green',
              'text-yellow-600 dark:text-yellow-400': color === 'yellow',
              'text-red-600 dark:text-red-400': color === 'red',
              'text-slate-600 dark:text-slate-400': color === 'slate'
            }
          ]"
        />
      </div>
      <div>
        <p class="text-sm text-slate-500 dark:text-slate-400">{{ title }}</p>
        <p class="text-2xl font-semibold text-slate-900 dark:text-white">{{ value }}</p>
        <p v-if="subtitle" class="text-sm text-slate-500 dark:text-slate-400">{{ subtitle }}</p>
      </div>
    </div>
  </div>
</template>
