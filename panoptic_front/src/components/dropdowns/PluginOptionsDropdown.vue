<script setup lang="ts">
import { PluginKey, usePanopticStore } from '@/data/panopticStore'
import Dropdown from './Dropdown.vue';
import { nextTick, ref } from 'vue';

const panoptic = usePanopticStore()

const props = defineProps<{
    plugin: PluginKey
}>()


const isUpdating = ref(false)
const isUpdateSucess = ref(false)

async function updatePlugin() {
    isUpdating.value = true
    isUpdateSucess.value = false
    await nextTick()
    try {
        let res = await panoptic.updatePlugin(props.plugin.name)
        isUpdateSucess.value = res
    }
    catch {
    }
    isUpdating.value = false
}
</script>

<template>
    <Dropdown>
        <template #button>
            <div>
                <span class="bb">
                    {{ props.plugin.name }}
                    <i class="bi bi-three-dots-vertical"></i>
                </span>
            </div>
        </template>
        <template #popup>
            <div class="p-2">
                <div class="bb" @click="panoptic.delPlugin(props.plugin.name)">
                    <i class="bi bi-trash me-1" /> {{ $t('plugin.remove') }}
                </div>
                <div class="bb" @click="updatePlugin">
                    <i v-if="!isUpdating && !isUpdateSucess" class="bi bi-arrow-clockwise me-1" />
                    <div v-if="isUpdating && !isUpdateSucess" class="spinner-border spinner-border-sm text-primary"
                        role="status" style="margin-right: 5px;">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <i v-if="isUpdateSucess" class="bi bi-check2 text-success me-1"></i>
                    <span v-if="props.plugin.source">{{ $t('plugin.update') }}</span>
                    <span v-else>{{ $t('plugin.update_local') }}</span>
                </div>

                <div class="custom-hr mt-1 mb-1" />
                <div style="max-width: 200px; word-break: break-all;">
                    <div v-if="plugin.path">
                        <span>{{ $t('plugin.path') }}</span>
                        <br />
                        <span class="text-secondary">{{ plugin.path }}</span>
                    </div>
                    <div v-if="plugin.source">
                        <span>{{ $t('plugin.source') }}</span>
                        <br />
                        <span class="text-secondary">{{ plugin.type }} {{ plugin.source }}</span>
                    </div>
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped></style>