<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTauriLauncherStore } from '@/data/tauriLauncherStore'

// confirm: the backend is running (home view), switching stops it and its ongoing tasks
const props = defineProps<{ confirm?: boolean }>()

const launcher = useTauriLauncherStore()
const { t } = useI18n()
const error = ref<string>(null)

async function change(mode: 'open' | 'new' | 'default') {
    error.value = null
    try {
        const path = mode === 'default' ? null : await launcher.browseDb(mode)
        if (mode !== 'default' && !path) return
        if (props.confirm) {
            const { ask } = await import('@tauri-apps/plugin-dialog')
            if (!await ask(t('launcher.db.confirm'), { title: 'Panoptic', kind: 'warning' })) return
        }
        await launcher.switchDb(path)
    } catch (e) {
        error.value = String(e)
    }
}
</script>

<template>
    <div v-if="launcher.status" class="db-selector small">
        <div class="text-secondary text-break">
            <i class="bi bi-database me-1"></i>
            {{ $t('launcher.db.current') }} : {{ launcher.status.dbPath }}
            <span v-if="launcher.status.dbIsDefault">({{ $t('launcher.db.default') }})</span>
        </div>
        <div v-if="launcher.status.backendExternal" class="text-secondary">{{ $t('launcher.db.external') }}</div>
        <div v-else class="d-flex gap-2 justify-content-center flex-wrap mt-1">
            <a href="#" @click.prevent="change('open')">{{ $t('launcher.db.open') }}</a>
            <a href="#" @click.prevent="change('new')">{{ $t('launcher.db.new') }}</a>
            <a v-if="!launcher.status.dbIsDefault" href="#" @click.prevent="change('default')">
                {{ $t('launcher.db.use_default') }}
            </a>
        </div>
        <div v-if="error" class="text-danger text-break">{{ error }}</div>
    </div>
</template>

<style scoped>
.db-selector {
    text-align: center;
}

.db-selector a {
    color: inherit;
}
</style>
