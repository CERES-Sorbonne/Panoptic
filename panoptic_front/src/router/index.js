import { createRouter, createWebHistory } from 'vue-router'
import PanopticView from '../views/PanopticView.vue'
import TestView from '../views/TestView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'compute',
      component: PanopticView
    },
    {
      path: '/test',
      name: 'test',
      component: TestView
    }
  ]
})

export default router
