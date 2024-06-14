import { createApp } from 'vue'
import { createPinia } from 'pinia'
import messages from './locales/conf'

import {createI18n} from 'vue-i18n'
import VueTour from 'vue3-tour'

import App from './App.vue'

import "bootstrap/dist/css/bootstrap.min.css"
import "bootstrap-icons/font/bootstrap-icons.css"
import "bootstrap"
import '@/assets/customize.scss'
import '@vueform/toggle/themes/default.css'
import 'vue3-tour/dist/vue3-tour.css'
// import './components/vuefinder/dist/style.css'
// import VueFinder from './components/vuefinder/src/index.js'
import VueVirtualScroller from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import VueApexCharts from "vue3-apexcharts";

const i18n = createI18n({
    legacy: false,
    locale: 'fr', // set locale
    fallbackLocale: 'en', // set fallback locale
    messages,
})

const pinia = createPinia()

const app = createApp(App)
app.use(pinia)
app.use(VueVirtualScroller)
app.use(VueApexCharts)

import router from './router'
app.use(router)
// app.use(VueFinder)
app.use(i18n)
app.use(VueTour).provide('tours', app.config.globalProperties.$tours)
app.mount('#app')
