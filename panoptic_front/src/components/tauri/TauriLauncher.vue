<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useTauriLauncherStore } from '@/data/tauriLauncherStore'

const launcher = useTauriLauncherStore()

const logPanel = ref<HTMLElement>(null)

const stepLabel = computed(() => {
    switch (launcher.phase) {
        case 'checking': return 'launcher.checking'
        case 'installing-uv': return 'launcher.installing_uv'
        case 'creating-venv': return 'launcher.creating_venv'
        case 'installing-panoptic': return 'launcher.installing_panoptic'
        case 'updating': return 'launcher.updating'
        case 'launching': return 'launcher.launching'
        default: return null
    }
})

watch(() => launcher.logs.length, async () => {
    await nextTick()
    if (logPanel.value) logPanel.value.scrollTop = logPanel.value.scrollHeight
})
</script>

<template>
    <div class="launcher d-flex flex-column align-items-center justify-content-center">
        <div class="launcher-card">
            <h4 class="mb-3 text-center">Panoptic</h4>

            <div v-if="stepLabel" class="text-center mb-2">
                <div class="spinner-border spinner-border-sm me-2" role="status"></div>
                {{ $t(stepLabel) }}
            </div>

            <div v-if="launcher.phase === 'ask-install-dir'" class="mb-2">
                <p>{{ $t('launcher.folder.question') }}</p>
                <p class="text-secondary small">{{ $t('launcher.folder.hint') }}</p>
                <div class="d-flex gap-2 align-items-center mb-2">
                    <input type="text" class="form-control form-control-sm" v-model="launcher.installDir" />
                    <button class="btn btn-sm btn-secondary text-nowrap" @click="launcher.browseInstallDir()">
                        {{ $t('launcher.folder.browse') }}
                    </button>
                </div>
                <div class="text-center">
                    <button class="btn btn-sm btn-primary" :disabled="!launcher.installDir"
                        @click="launcher.answer(true)">
                        {{ $t('launcher.folder.confirm') }}
                    </button>
                </div>
            </div>

            <div v-if="launcher.phase === 'ask-gpu'" class="mb-2">
                <p>{{ $t('launcher.gpu.question') }}</p>
                <p class="text-secondary small">{{ $t('launcher.gpu.hint') }}</p>
                <div class="d-flex gap-2 justify-content-center">
                    <button class="btn btn-sm btn-primary" @click="launcher.answer(true)">
                        {{ $t('launcher.gpu.yes') }}
                    </button>
                    <button class="btn btn-sm btn-secondary" @click="launcher.answer(false)">
                        {{ $t('launcher.gpu.no') }}
                    </button>
                </div>
            </div>

            <div v-if="launcher.phase === 'ask-update'" class="mb-2">
                <p>
                    {{ $t('launcher.update.question') }}
                    <span v-if="launcher.updateInfo?.latestVersion" class="text-nowrap">
                        ({{ launcher.updateInfo.installedVersion }} → {{ launcher.updateInfo.latestVersion }})
                    </span>
                </p>
                <div class="d-flex gap-2 justify-content-center">
                    <button class="btn btn-sm btn-primary" @click="launcher.answer(true)">
                        {{ $t('launcher.update.yes') }}
                    </button>
                    <button class="btn btn-sm btn-secondary" @click="launcher.answer(false)">
                        {{ $t('launcher.update.no') }}
                    </button>
                </div>
            </div>

            <div v-if="launcher.phase === 'error'" class="mb-2">
                <p class="text-danger">{{ $t('launcher.error') }}</p>
                <pre class="error-message">{{ launcher.error }}</pre>
                <div class="text-center">
                    <button class="btn btn-sm btn-primary" @click="launcher.retry()">
                        {{ $t('launcher.retry') }}
                    </button>
                </div>
            </div>

            <pre v-if="launcher.logs.length" ref="logPanel" class="log-panel"><span v-for="(log, i) in launcher.logs"
                :key="i" :class="{ 'log-stderr': log.stream === 'stderr' }">{{ log.line }}&#10;</span></pre>

            <div class="text-secondary small text-center mt-2">
                <span v-if="launcher.uiVersion">UI v{{ launcher.uiVersion }}</span>
                <span v-if="launcher.status?.installedVersion"> — panoptic v{{ launcher.status.installedVersion }}</span>
                <div v-if="launcher.status?.logPath">{{ $t('launcher.logs') }} : {{ launcher.status.logPath }}</div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.launcher {
    height: 100vh;
    background-color: var(--background-color);
    color: var(--text-color);
}

.launcher-card {
    width: 620px;
    max-width: 90vw;
    padding: var(--card-padding);
    border: var(--hr);
    border-radius: var(--card-border-radius);
    background-color: var(--light-background);
}

.log-panel {
    margin-top: 0.5rem;
    height: 220px;
    overflow-y: auto;
    font-size: 0.75rem;
    padding: 0.5rem;
    border: var(--hr);
    border-radius: var(--card-border-radius);
    background-color: var(--background-color);
    white-space: pre-wrap;
    word-break: break-all;
}

.log-stderr {
    color: var(--disabled-color);
}

.error-message {
    max-height: 100px;
    overflow-y: auto;
    font-size: 0.75rem;
    white-space: pre-wrap;
    color: var(--text-color);
}
</style>
