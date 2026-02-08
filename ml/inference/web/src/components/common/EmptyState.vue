<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{
  title: string
  description: string
  actionLabel?: string
  icon?: Component
}>()

const emit = defineEmits<{
  action: []
}>()
</script>

<template>
  <div class="card p-12 text-center">
    <component
      v-if="icon"
      :is="icon"
      class="w-12 h-12 mx-auto text-slate-400 dark:text-slate-500 mb-4"
    />
    <h3 class="text-lg font-medium text-slate-900 dark:text-white mb-2">{{ title }}</h3>
    <p class="text-slate-500 dark:text-slate-400 mb-6 max-w-sm mx-auto">{{ description }}</p>
    <button
      v-if="actionLabel"
      @click="emit('action')"
      class="btn-primary"
    >
      {{ actionLabel }}
    </button>
  </div>
</template>
