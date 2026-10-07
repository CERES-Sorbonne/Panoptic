<script setup lang="ts">
import { ParamDescription, PluginDescription } from '@/data/models';
import { computed, ref, watch } from 'vue';
import ParamInput from '@/components/inputs/ParamInput.vue';
import SectionDivider from '../utils/SectionDivider.vue';
import { useProjectStore } from '@/data/stores/projectStore';
import { deepCopy } from '@/utils/utils';

const project = useProjectStore()

const props = defineProps<{
    plugin: PluginDescription
}>()

// Copy of the plugin's base params. ParamInput writes the edited values into it.
const localParams = ref<ParamDescription[]>([])

const savedParams = computed(() => props.plugin.baseParams?.params ?? [])

// Values are compared as JSON: some of them are objects (vector types for example)
const changed = computed(() => localParams.value.some((p, i) =>
    JSON.stringify(p.defaultValue ?? null) !== JSON.stringify(savedParams.value[i]?.defaultValue ?? null)
))

const applying = ref(false)
const applied = ref(false)
let appliedTimer: ReturnType<typeof setTimeout> | undefined

function resetLocalParams() {
    localParams.value = deepCopy(savedParams.value)
}

async function applyLocalParams() {
    if (!changed.value || applying.value) return
    const toSend = {}
    for (let param of localParams.value) {
        toSend[param.id] = param.defaultValue
    }
    applying.value = true
    try {
        // The store replaces the plugin list, which resets localParams through the watcher
        await project.setPluginParams(props.plugin.name, toSend)
        applied.value = true
        clearTimeout(appliedTimer)
        appliedTimer = setTimeout(() => applied.value = false, 2000)
    } finally {
        applying.value = false
    }
}

// Starting a plugin queues a LoadPluginTask. Its state arrives through `tasks`,
// and `plugins_info` follows once it is loaded (or failed to load).
const busy = ref(false)
const loading = computed(() => (project.state.tasks ?? []).some(t => t.key === 'LoadPluginTask' && !t.finished))

async function toggleRunning() {
    busy.value = true
    try {
        if (props.plugin.running) await project.stopPlugin(props.plugin.name)
        else await project.startPlugin(props.plugin.name)
    } finally {
        busy.value = false
    }
}

watch(() => props.plugin, resetLocalParams, { immediate: true })
</script>

<template>
    <div v-if="props.plugin" class="main">
        <div class="d-flex align-items-center">
            <span class="plugin-name">{{ props.plugin.name }}</span>
            <span class="ms-2 status" :class="props.plugin.running ? 'text-success' : 'text-secondary'">
                <i class="bi" :class="props.plugin.running ? 'bi-play-circle-fill' : 'bi-stop-circle'" />
                {{ props.plugin.running ? $t('modals.settings.plugin_running') : $t('modals.settings.plugin_stopped') }}
            </span>
            <div class="flex-grow-1"></div>
            <span v-if="busy || (!props.plugin.running && loading)" class="spinner-border spinner-border-sm text-secondary" />
            <span v-else class="bb" @click="toggleRunning">
                <i class="bi me-1" :class="props.plugin.running ? 'bi-stop-fill' : 'bi-play-fill'" />
                {{ props.plugin.running ? $t('modals.settings.plugin_stop') : $t('modals.settings.plugin_start') }}
            </span>
        </div>
        <div v-if="props.plugin.description" class="text-secondary description">{{ props.plugin.description }}</div>
        <div v-if="!props.plugin.running" class="text-secondary description mt-1">{{ $t('modals.settings.plugin_stopped_hint') }}</div>

        <template v-if="props.plugin.running">
            <SectionDivider class="mt-3">{{ $t('modals.settings.baseSettings') }}</SectionDivider>
            <div v-if="props.plugin.baseParams?.description" class="text-secondary description mb-1">
                {{ props.plugin.baseParams.description }}
            </div>
            <div v-if="!localParams.length" class="text-secondary description">{{ $t('modals.settings.pluginNoSettings') }}</div>
            <template v-else>
                <form class="params-grid" @submit.prevent="applyLocalParams">
                    <ParamInput v-for="param in localParams" :key="param.name" :input="param" :source="props.plugin.name"
                        :max-width="220" />
                </form>
                <div class="ms-3 mt-3">
                    <SectionDivider>
                        <span class="bbb me-2" :class="{ disabled: !changed || applying }" @click="resetLocalParams">
                            {{ $t('modals.settings.cancel') }}
                        </span>
                        <span class="bbb" :class="{ disabled: !changed || applying }" @click="applyLocalParams">
                            {{ $t('modals.settings.apply') }}
                        </span>
                        <span v-if="applying" class="ms-2 spinner-border spinner-border-sm text-primary" />
                        <span v-else-if="applied && !changed" class="ms-2 text-success">
                            <i class="bi bi-check" />{{ $t('modals.settings.applied') }}
                        </span>
                    </SectionDivider>
                </div>
            </template>
        </template>
    </div>
</template>

<style scoped>
.main {
    padding: 5px 10px;
}

.plugin-name {
    font-weight: 600;
}

.status,
.description {
    font-size: 13px;
}

.params-grid {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 4px 16px;
    align-items: center;
    padding: 4px 16px;
}

.disabled {
    opacity: 0.5;
    pointer-events: none;
}
</style>
