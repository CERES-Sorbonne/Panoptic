import { createApp } from 'vue'

import App from './App.vue'
import router from './router'

import "bootstrap/dist/css/bootstrap.min.css"
import "bootstrap-icons/font/bootstrap-icons.css"
import "bootstrap"
import '@/assets/customize.scss'
import '@vueform/toggle/themes/default.css'


const app = createApp(App)

app.use(router)

app.mount('#app')
