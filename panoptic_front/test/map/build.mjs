/**
 * Bundle the map suite (node:test) and the grid bench for node, with the project's vite (only the
 * `@/` alias needs resolving: the modules under test are pure).
 */
import { build } from 'vite'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const here = path.dirname(fileURLToPath(import.meta.url))
const front = path.resolve(here, '../..')
const src = path.join(front, 'src')

await build({
    root: front,
    configFile: false,
    mode: 'development',
    logLevel: 'warn',
    resolve: {
        alias: [{ find: /^@\//, replacement: src + '/' }],
    },
    build: {
        ssr: true,
        outDir: path.join(here, '.build'),
        emptyOutDir: true,
        copyPublicDir: false,
        target: 'node22',
        minify: false,
        sourcemap: false,
        rollupOptions: {
            external: [/^node:/],
            input: {
                suite: path.join(here, 'suite.ts'),
                bench: path.join(here, 'bench.ts'),
            },
            output: {
                format: 'es',
                entryFileNames: '[name].mjs',
                chunkFileNames: '[name]-[hash].mjs',
            },
        },
    },
})
