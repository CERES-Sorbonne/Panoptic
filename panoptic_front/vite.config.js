import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import path from 'node:path';
import vue from '@vitejs/plugin-vue'

const replaceFiles = [path.join(__dirname, '/src/locales/fr.json')];

// https://vitejs.dev/config/
export default defineConfig({
    base: '/',
    server: {
        fs: {
            // Allow serving files from one level up to the project root
            allow: ['..'],
        },
    },
    // assetsInclude: replaceFiles,
    plugins: [
        vue(),
    ],
    resolve: {
        alias: {
            '@': fileURLToPath(new URL('./src', import.meta.url))
        }
    },
    build: {
        outDir: '../panoptic_back/panoptic/html',
        emptyOutDir: true
    },
    define: {
        // enable hydration mismatch details in production build
        __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: 'true'
    }
})


