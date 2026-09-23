import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import path from 'node:path';
import vue from '@vitejs/plugin-vue'

const replaceFiles = [path.join(__dirname, '/src/locales/fr.json')];

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
    base: '/',
    server: {
        // tauri dev expects the fixed devUrl 5173: fail instead of silently moving ports
        port: 5173,
        strictPort: true,
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
        // mode 'tauri': build embarqué dans l'exe Tauri, ne doit pas écraser le build du paquet pip
        outDir: mode === 'tauri' ? 'dist-tauri' : '../panoptic_back/panoptic/html',
        emptyOutDir: true
    },
    define: {
        // enable hydration mismatch details in production build
        __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: 'true'
    }
}))


