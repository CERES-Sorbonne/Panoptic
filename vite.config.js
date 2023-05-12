import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default ({mode}) => {
    process.env = Object.assign(process.env, loadEnv(mode, process.cwd(), ''));
    return defineConfig({

        plugins: [vue()],
        resolve: {
            alias: {
                '@': fileURLToPath(new URL('./src', import.meta.url))
            },
        },
        // server: {
        //     // host: '0.0.0.0',
        //     proxy: {
        //         '/api': {
        //             target: "http://127.0.0.1:8000/",
        //             changeOrigin: true,
        //             secure: false,
        //             rewrite: (path) => path.replace(/^\/api/, '')
        //         },
        //         '/images': {
        //             target: "http://127.0.0.1:8000/",
        //             changeOrigin: true,
        //             secure: false,
        //         },
        //     }
        // },
    })
}

