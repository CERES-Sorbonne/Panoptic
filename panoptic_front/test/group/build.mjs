/**
 * Bundle the suite (node:test) and the simulation (standalone) for node.
 *
 * Node 24 strips types on its own, but it cannot run these modules directly: they use the `@/`
 * alias, extensionless relative imports and `import.meta.env`, and `@/data/stores/*` are pinia
 * stores that drag in the router and axios. So the suite is bundled with the project's own vite
 * (no extra dependency), with the stores aliased to the headless stubs in harness/stubs and
 * DEV on, so ClusterOverlay.checkInvariants runs.
 */
import { build } from 'vite'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const here = path.dirname(fileURLToPath(import.meta.url))
const front = path.resolve(here, '../..')
const src = path.join(front, 'src')
const stubs = path.join(here, 'harness/stubs')

const alias = (name) => ({
    find: new RegExp(`^@/data/stores/${name}$`),
    replacement: path.join(stubs, `${name}.ts`),
})

await build({
    root: front,
    configFile: false,
    mode: 'development',
    logLevel: 'warn',
    resolve: {
        alias: [
            alias('columnStore'),
            alias('dataStore'),
            alias('actionStore'),
            { find: /^vue-router$/, replacement: path.join(stubs, 'router.ts') },
            { find: /^@\//, replacement: src + '/' },
        ],
    },
    define: {
        // Belt and braces: `mode: development` already gives DEV, but the invariant checks
        // hang off it, so pin it rather than trust the mode plumbing.
        'import.meta.env.DEV': 'true',
        // debugGroup reads window.__grpDebug before falling back to DEV; without this the DEV
        // build would print every grouping trace.
        'window.__grpDebug': 'false',
        // Absolute path to src/, so the static checks can read the real component files.
        __SRC_DIR__: JSON.stringify(src),
    },
    build: {
        // Two entries: the node:test suite and the standalone simulation. `ssr: true` with an
        // explicit rollup input is how vite takes more than one.
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
                sim: path.join(here, 'sim/main.ts'),
            },
            output: {
                format: 'es',
                entryFileNames: '[name].mjs',
                chunkFileNames: '[name]-[hash].mjs',
            },
        },
    },
})
