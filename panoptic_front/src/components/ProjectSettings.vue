<script setup lang="ts">
import { FunctionDescription, ProjectSettings } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import { objValues } from '@/utils/utils';
import { onMounted, computed, watch, reactive } from 'vue';

const project = useProjectStore()

const localSettings = reactive({} as ProjectSettings)



const changed = computed(() => {
    for (let k in localSettings) {
        if (localSettings[k] !== project.data.settings[k]) {
            return true
        }
    }
    return false
})

function updateLocal() {
    Object.assign(localSettings, project.data.settings)
}

function applyChange() {
    project.updateSettings(localSettings)
}

onMounted(updateLocal)
watch(() => project.data.settings, updateLocal)

</script>

<template>
    <div v-if="localSettings" class="main">
        <h4 class="text-center">Project</h4>
        <!-- <div class="custom-hr mb-3" /> -->
        <table>
            <tr>
                <td>Save small image</td>
                <td><input type="checkbox" v-model="localSettings.saveImageSmall" /></td>
            </tr>
            <tr>
                <td>Save medium image</td>
                <td><input type="checkbox" v-model="localSettings.saveImageMedium" /></td>
            </tr>
            <tr>
                <td>Save large image</td>
                <td>
                    <input type="checkbox" v-model="localSettings.saveImageLarge" />
                </td>
            </tr>
        </table>

        <div v-if="changed" class="d-flex changed">
            <div class="flex-grow-1"></div>
            <div class="base-btn me-3" @click="updateLocal">Reset</div>
            <div class="base-btn" @click="applyChange">Update</div>
        </div>
    </div>
</template>

<style scoped>
.main {
    border: 1px solid var(--border-color);
    border-radius: 3px;
    /* padding: 5px; */
}

.changed {
    border-top: 1px solid var(--border-color);
    padding: 5px;
}
</style>