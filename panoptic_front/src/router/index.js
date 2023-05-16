import { createRouter, createWebHistory } from 'vue-router'
import PanopticView from '../views/PanopticView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'compute',
      component: PanopticView
    }
  ]
})

export default router