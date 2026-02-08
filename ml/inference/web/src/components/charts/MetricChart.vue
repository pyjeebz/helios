<script setup lang="ts">
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
  Legend
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
  Legend
)

const props = defineProps<{
  title: string
  data: number[]
  labels: string[]
  unit?: string
  color?: string
  filled?: boolean
}>()

const chartData = computed(() => ({
  labels: props.labels,
  datasets: [
    {
      label: props.title,
      data: props.data,
      borderColor: props.color || '#8b5cf6',
      backgroundColor: props.filled 
        ? (props.color || '#8b5cf6') + '20' 
        : 'transparent',
      fill: props.filled || false,
      tension: 0.4,
      pointRadius: 0,
      pointHoverRadius: 4
    }
  ]
}))

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: false
    },
    tooltip: {
      callbacks: {
        label: (ctx: any) => `${ctx.parsed.y.toFixed(1)}${props.unit || ''}`
      }
    }
  },
  scales: {
    x: {
      grid: {
        display: false
      },
      ticks: {
        maxTicksLimit: 8,
        color: '#94a3b8'
      }
    },
    y: {
      grid: {
        color: '#e2e8f0'
      },
      ticks: {
        callback: (val: number) => `${val}${props.unit || ''}`,
        color: '#94a3b8'
      }
    }
  }
}))
</script>

<template>
  <div class="card p-6">
    <h3 class="text-lg font-medium text-slate-900 dark:text-white mb-4">{{ title }}</h3>
    <div class="h-64">
      <Line :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>
