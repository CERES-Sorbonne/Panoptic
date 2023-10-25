import { createApp } from 'vue'
import messages from './locales/conf'

import {createI18n} from 'vue-i18n'

import App from './App.vue'
import router from './router'

import "bootstrap/dist/css/bootstrap.min.css"
import "bootstrap-icons/font/bootstrap-icons.css"
import "bootstrap"
import '@/assets/customize.scss'
import '@vueform/toggle/themes/default.css'


const i18n = createI18n({
    locale: 'fr', // set locale
    fallbackLocale: 'en', // set fallback locale
    messages,
})

const app = createApp(App)

// Make BootstrapVue available throughout your project
// Optionally install the BootstrapVue icon components plugin

app.use(router)
app.use(i18n)
app.mount('#app')
