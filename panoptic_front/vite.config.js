import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import path from 'node:path';
import vue from '@vitejs/plugin-vue'

const replaceFiles = [path.join(__dirname, '/src/locales/fr.json')];

// https://vitejs.dev/config/
export default defineConfig({
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
    }
})


