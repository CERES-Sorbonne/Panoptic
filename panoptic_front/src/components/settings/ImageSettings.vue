<script setup lang="ts">
import { FunctionDescription, ProjectSettings } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import { objValues } from '@/utils/utils';
import { onMounted, computed, watch, reactive } from 'vue';
import SectionDivider from '../utils/SectionDivider.vue';

const project = useProjectStore()

const props = defineProps<{
    changed: boolean
}>()

const emits = defineEmits(['update:changed'])

defineExpose({
    cancel,
    apply
})

const localSettings = reactive({} as ProjectSettings)



const changed = computed(() => {
    for (let k in localSettings) {
        if (localSettings[k] !== project.state.settings[k]) {
            return true
        }
    }
    return false
})

function cancel() {
    updateLocal()
}

function apply() {
    project.updateSettings(localSettings)
}

function updateLocal() {
    Object.assign(localSettings, project.state.settings)
}

onMounted(updateLocal)
watch(() => project.state.settings, updateLocal)
watch(changed, (val) => {
    emits('update:changed', val)
})

</script>

<template>
    <div v-if="localSettings" class="main">
        <SectionDivider class="">{{$t('modals.settings.thumbnailStorage')}}</SectionDivider>
        <table class="m-2">
            <tbody>
                <tr>
                    <td class="pe-2">
                        <input type="checkbox" v-model="localSettings.saveImageSmall" class="me-3" />
                        <span>{{$t('modals.settings.small')}}</span>
                    </td>
                    <td></td>
                    <td class="ps-2">
                        <input style="text-align: right; width: 50px;" type="number"
                            v-model="localSettings.imageSmallSize" />
                        {{$t('modals.settings.px')}}
                    </td>
                </tr>
                <tr>
                    <td class="pe-2">
                        <input type="checkbox" v-model="localSettings.saveImageMedium" class="me-3" />
                        <span>{{$t('modals.settings.medium')}}</span>
                    </td>
                    <td></td>
                    <td class="ps-2">
                        <input style="text-align: right; width: 50px;" type="number"
                            v-model="localSettings.imageMediumSize" />
                        px
                    </td>
                </tr>
                <tr>
                    <td class="pe-2">
                        <input type="checkbox" v-model="localSettings.saveImageLarge" class="me-3" />
                        <span>{{$t('modals.settings.large')}}</span>
                    </td>
                    <td></td>
                    <td class="ps-2">
                        <input style="text-align: right; width: 50px;" type="number"
                            v-model="localSettings.imageLargeSize" />
                        px
                    </td>
                </tr>
            </tbody>
        </table>
        <SectionDivider class="">{{$t('modals.settings.imageStorage')}}</SectionDivider>
        <table class="m-2">
            <tbody>
                <tr>
                    <td class="pe-2">
                        <input type="checkbox" v-model="localSettings.saveFileRaw" class="me-3" />
                        <span>{{$t('modals.settings.fullImage')}}</span>
                    </td>
                    <td></td>
                    <td></td>
                </tr>
            </tbody>
        </table>
    </div>
</template>

<style scoped>
.main {
    padding: 5px;
}

.changed {
    border-top: 1px solid var(--border-color);
    padding: 5px;
}
</style>