import { defineStore } from "pinia"
import { ref } from "vue"

// True when running inside the Tauri desktop app
export const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

export type LauncherPhase = 'checking' | 'installing-uv' | 'creating-venv' | 'ask-gpu'
    | 'installing-panoptic' | 'ask-update' | 'updating' | 'launching' | 'ready' | 'error'

export interface SetupStatus {
    backendRunning: boolean
    uvInstalled: boolean
    venvExists: boolean
    panopticInstalled: boolean
    installedVersion?: string
    os: string
}

export interface UpdateInfo {
    updateAvailable: boolean
    installedVersion?: string
    latestVersion?: string
}

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

    let listening = false
    let answerResolve: (value: boolean) => void = null

    // resolved by answer() when the user clicks a button in the ask-gpu / ask-update cards
    function waitForAnswer(): Promise<boolean> {
        return new Promise(resolve => { answerResolve = resolve })
    }

    function answer(value: boolean) {
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
            phase.value = 'creating-venv'
            await invoke('create_venv')
            if (!status.value.panopticInstalled) {
                let gpuMode = 'default'
                if (status.value.os !== 'macos') {
                    phase.value = 'ask-gpu'
                    gpuMode = (await waitForAnswer()) ? 'cuda' : 'cpu'
                }
                phase.value = 'installing-panoptic'
                await invoke('install_panoptic', { gpuMode })
            } else {
                updateInfo.value = await invoke<UpdateInfo>('check_update')
                if (updateInfo.value.updateAvailable) {
                    phase.value = 'ask-update'
                    if (await waitForAnswer()) {
                        phase.value = 'updating'
                        await invoke('update_panoptic')
                        status.value = await invoke<SetupStatus>('check_status')
                    }
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

    async function retry() {
        const { invoke } = await import('@tauri-apps/api/core')
        error.value = null
        try { await invoke('stop_backend') } catch { }
        // start() re-checks the status, so completed steps are skipped
        await start()
    }

    return { phase, logs, error, status, updateInfo, uiVersion, start, retry, answer }
})
