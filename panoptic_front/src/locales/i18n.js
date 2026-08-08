import { createI18n } from 'vue-i18n'
import messages from './conf'

// Created here rather than in main.js so non-component modules (stores, builders)
// can translate via i18n.global.t without importing the app entrypoint.
export const i18n = createI18n({
    legacy: false,
    locale: 'fr', // set locale
    fallbackLocale: 'en', // set fallback locale
    messages,
})

export const t = (key) => i18n.global.t(key)

export default i18n
