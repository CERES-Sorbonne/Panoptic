import { createApp } from 'vue'

import App from './App.vue'
import router from './router'

import "bootstrap/dist/css/bootstrap.min.css"
import "bootstrap-icons/font/bootstrap-icons.css"
import "bootstrap"
import '@/assets/customize.scss'
// import VueVirtualScroller from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'


const app = createApp(App)

// Make BootstrapVue available throughout your project
// Optionally install the BootstrapVue icon components plugin

app.use(router)
// app.use(VueVirtualScroller)

app.mount('#app')
