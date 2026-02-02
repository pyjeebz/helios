import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: () => import('@/components/layout/Layout.vue'),
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('@/views/Dashboard.vue')
        },
        {
          path: 'predictions',
          name: 'predictions',
          component: () => import('@/views/Predictions.vue')
        },
        {
          path: 'anomalies',
          name: 'anomalies',
          component: () => import('@/views/Anomalies.vue')
        },
        {
          path: 'agents',
          name: 'agents',
          component: () => import('@/views/Agents.vue')
        },
        {
          path: 'deployments',
          name: 'deployments',
          component: () => import('@/views/Deployments.vue')
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/Settings.vue')
        }
      ]
    }
  ]
})

export default router
