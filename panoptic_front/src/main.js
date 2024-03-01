import { createApp } from 'vue'
import { createPinia } from 'pinia'
import messages from './locales/conf'

import {createI18n} from 'vue-i18n'

import App from './App.vue'

import "bootstrap/dist/css/bootstrap.min.css"
import "bootstrap-icons/font/bootstrap-icons.css"
import "bootstrap"
import '@/assets/customize.scss'
import '@vueform/toggle/themes/default.css'
import VueVirtualScroller from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'

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

import router from './router'
app.use(router)
// app.use(VueFinder)
app.use(i18n)

app.mount('#app')
