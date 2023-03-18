import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [vue()],
    resolve: {
        alias: {
            '@': fileURLToPath(new URL('./src', import.meta.url))
        },
    },
    server: {
        proxy: {
        '/images': {
            target: 'http://localhost:8000/',
            changeOrigin: true,
            secure: false,
            rewrite: (path) => {
                // let p = path.replace(/^\/images/, '')
                // console.log(path)
                return path
            }
        },
        }
    },
})
