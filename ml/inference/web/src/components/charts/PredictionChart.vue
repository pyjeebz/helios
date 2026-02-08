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
  subtitle?: string
  historicalData: number[]
  forecastData: number[]
  upperBound: number[]
  lowerBound: number[]
  labels: string[]
  prediction?: {
    peakValue: number
    peakTime: string
    confidence: number
    horizon: string
  } | null
}>()

const chartData = computed(() => {
  const historicalLen = props.historicalData.length
  
  // Pad forecast data to align with labels
  const fullForecast = [...Array(historicalLen - 1).fill(null), 
    props.historicalData[historicalLen - 1], // Connect point
    ...props.forecastData
  ]
  const fullUpper = [...Array(historicalLen - 1).fill(null),
    props.historicalData[historicalLen - 1],
    ...props.upperBound
  ]
  const fullLower = [...Array(historicalLen - 1).fill(null),
    props.historicalData[historicalLen - 1],
    ...props.lowerBound
  ]

  return {
    labels: props.labels,
    datasets: [
      {
        label: 'Historical',
        data: [...props.historicalData, ...Array(props.forecastData.length).fill(null)],
        borderColor: '#3b82f6',
        backgroundColor: 'transparent',
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 4
      },
      {
        label: 'Forecast',
        data: fullForecast,
        borderColor: '#8b5cf6',
        borderDash: [5, 5],
        backgroundColor: 'transparent',
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 4
      },
      {
        label: 'Upper Bound',
        data: fullUpper,
        borderColor: 'rgba(139, 92, 246, 0.3)',
        backgroundColor: 'rgba(139, 92, 246, 0.1)',
        fill: '+1',
        tension: 0.4,
        pointRadius: 0
      },
      {
        label: 'Lower Bound',
        data: fullLower,
        borderColor: 'rgba(139, 92, 246, 0.3)',
        backgroundColor: 'transparent',
        tension: 0.4,
        pointRadius: 0
      }
    ]
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: true,
      position: 'top' as const,
      labels: {
        filter: (item: any) => item.text !== 'Upper Bound' && item.text !== 'Lower Bound'
      }
    },
    tooltip: {
      callbacks: {
        label: (ctx: any) => ctx.parsed.y !== null ? `${ctx.parsed.y.toFixed(1)}%` : ''
      }
    }
  },
  scales: {
    x: {
      grid: { display: false },
      ticks: { maxTicksLimit: 10, color: '#94a3b8' }
    },
    y: {
      grid: { color: '#e2e8f0' },
      ticks: {
        callback: (val: number) => `${val}%`,
        color: '#94a3b8'
      }
    }
  }
}
</script>

<template>
  <div class="card p-6">
    <div class="flex items-center justify-between mb-4">
      <div>
        <h3 class="text-lg font-medium text-slate-900 dark:text-white">{{ title }}</h3>
        <p v-if="subtitle" class="text-sm text-slate-500 dark:text-slate-400">{{ subtitle }}</p>
      </div>
      <div v-if="prediction" class="text-right">
        <span class="text-sm text-slate-500 dark:text-slate-400">Confidence: </span>
        <span class="text-sm font-medium text-green-600">{{ (prediction.confidence * 100).toFixed(0) }}%</span>
      </div>
    </div>
    <div class="h-80">
      <Line :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>
