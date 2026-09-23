import { defineStore } from "pinia"
import { ref } from "vue"

// True when running inside the Tauri desktop app
export const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

export type LauncherPhase = 'checking' | 'installing-uv' | 'ask-install-dir' | 'creating-venv'
    | 'ask-gpu' | 'installing-panoptic' | 'ask-update' | 'updating' | 'launching' | 'ready' | 'error'

export interface SetupStatus {
    backendRunning: boolean
    uvInstalled: boolean
    venvExists: boolean
    panopticInstalled: boolean
    installedVersion?: string
    os: string
    logPath?: string
    installDir?: string
}

export interface UpdateInfo {
    updateAvailable: boolean
    installedVersion?: string
    latestVersion?: string
    latestIsDev: boolean
}

export type UpdateAnswer = boolean | 'skip-dev'

export interface LogLine {
    line: string
    stream: 'stdout' | 'stderr'
}

export const useTauriLauncherStore = defineStore('tauriLauncherStore', () => {
    const phase = ref<LauncherPhase>('checking')
    const logs = ref<LogLine[]>([])
    const error = ref<string>(null)
    const status = ref<SetupStatus>(null)
    const updateInfo = ref<UpdateInfo>(null)
    const uiVersion = ref<string>('')
    const installDir = ref<string>('')

    let listening = false
    let answerResolve: (value: UpdateAnswer) => void = null

    // resolved by answer() when the user clicks a button in the ask-* cards
    function waitForAnswer(): Promise<UpdateAnswer> {
        return new Promise(resolve => { answerResolve = resolve })
    }

    function answer(value: UpdateAnswer) {
        if (answerResolve) {
            answerResolve(value)
            answerResolve = null
        }
    }

    // forward webview JS errors to the terminal (tauri dev / stderr) for debugging
    function forwardErrors(invoke: (cmd: string, args?: any) => Promise<any>) {
        const send = (message: string) => invoke('frontend_log', { message }).catch(() => { })
        window.addEventListener('error', e =>
            send(`error: ${e.message} @ ${e.filename}:${e.lineno}`))
        window.addEventListener('unhandledrejection', e =>
            send(`unhandledrejection: ${e.reason?.stack ?? e.reason}`))
        const original = console.error
        console.error = (...args: any[]) => {
            original(...args)
            send(args.map(a => a instanceof Error ? (a.stack ?? a.message) : String(a)).join(' '))
        }
    }

    async function start() {
        const { invoke } = await import('@tauri-apps/api/core')
        try {
            if (!listening) {
                listening = true
                forwardErrors(invoke)
                const { listen } = await import('@tauri-apps/api/event')
                await listen<LogLine>('install-log', e => logs.value.push(e.payload))
                await listen<LogLine>('backend-log', e => logs.value.push(e.payload))
                import('@tauri-apps/api/app').then(m => m.getVersion())
                    .then(v => uiVersion.value = v).catch(() => { })
            }
            phase.value = 'checking'
            status.value = await invoke<SetupStatus>('check_status')
            if (status.value.backendRunning) {
                phase.value = 'ready'
                return
            }
            if (!status.value.uvInstalled) {
                phase.value = 'installing-uv'
                await invoke('install_uv')
            }
            if (!status.value.panopticInstalled) {
                // first install: let the user pick the install folder before creating the venv
                installDir.value = status.value.installDir ?? ''
                phase.value = 'ask-install-dir'
                await waitForAnswer()
                await invoke('set_install_dir', { path: installDir.value })
                status.value = await invoke<SetupStatus>('check_status')
                phase.value = 'creating-venv'
                await invoke('create_venv')
                let gpuMode = 'default'
                if (status.value.os !== 'macos') {
                    phase.value = 'ask-gpu'
                    gpuMode = (await waitForAnswer()) ? 'cuda' : 'cpu'
                }
                phase.value = 'installing-panoptic'
                await invoke('install_panoptic', { gpuMode })
            } else {
                phase.value = 'creating-venv'
                await invoke('create_venv')
                updateInfo.value = await invoke<UpdateInfo>('check_update')
                while (updateInfo.value?.updateAvailable) {
                    phase.value = 'ask-update'
                    const ans = await waitForAnswer()
                    if (ans === 'skip-dev') {
                        // persist the opt-out, then re-check with stable versions only
                        await invoke('set_skip_dev_updates')
                        updateInfo.value = await invoke<UpdateInfo>('check_update')
                        continue
                    }
                    if (ans) {
                        phase.value = 'updating'
                        await invoke('update_panoptic', { version: updateInfo.value.latestVersion ?? null })
                        status.value = await invoke<SetupStatus>('check_status')
                    }
                    break
                }
            }
            phase.value = 'launching'
            await invoke('launch_backend')
            phase.value = 'ready'
        } catch (e) {
            error.value = String(e)
            phase.value = 'error'
        }
    }

    async function browseInstallDir() {
        const { open } = await import('@tauri-apps/plugin-dialog')
        const picked = await open({
            directory: true,
            defaultPath: installDir.value || undefined,
        })
        if (typeof picked === 'string' && picked) {
            installDir.value = picked
        }
    }

    async function retry() {
        const { invoke } = await import('@tauri-apps/api/core')
        error.value = null
        try { await invoke('stop_backend') } catch { }
        // start() re-checks the status, so completed steps are skipped
        await start()
    }

    return { phase, logs, error, status, updateInfo, uiVersion, installDir, start, retry, answer, browseInstallDir }
})
