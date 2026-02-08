<script setup lang="ts">
defineProps<{
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info'
}>()
</script>

<template>
  <span
    :class="[
      'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
      {
        'bg-slate-100 text-slate-800 dark:bg-slate-700 dark:text-slate-300': variant === 'default' || !variant,
        'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400': variant === 'success',
        'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400': variant === 'warning',
        'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400': variant === 'error',
        'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400': variant === 'info'
      }
    ]"
  >
    <slot />
  </span>
</template>
