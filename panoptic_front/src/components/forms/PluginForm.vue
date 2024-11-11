<script setup lang="ts">
import { ModalId, PluginAddPayload } from '@/data/models';
import { usePanopticStore } from '@/data/panopticStore';
import { useProjectStore } from '@/data/projectStore';
import { sleep } from '@/utils/utils';
import { computed, nextTick, ref } from 'vue';

const panoptic = usePanopticStore()

const emits = defineEmits(['cancel'])

defineExpose({
    setPanopticMl
})

const mode = ref('github')
const gitUrl = ref('')
const localPath = ref('')
const pluginName = ref('')
const isLoading = ref(false)

const takenNames = computed(() => panoptic.data.plugins.map(p => p.name))
const isNameValid = computed(() => {
    if (pluginName.value == '') return false
    if (takenNames.value.includes(pluginName.value)) return false
    return true
})

const showName = computed(() => (mode.value == "github" && gitUrl.value.length > 0) || (mode.value == "local" && localPath.value.length > 0))
const showLoad = computed(() => showName.value && isNameValid.value)

const helpMessage = computed(() => {
    if (showName.value && takenNames.value.includes(pluginName.value)) {
        return 'main.home.plugins.error_name_not_unique'
    }
    if (showName.value) {
        return 'main.home.plugins.require_unique_name'
    }
    if (mode.value == 'github') {
        return 'main.home.plugins.require_url'
    }
    return 'main.home.plugins.require_folder'
})

function setLocalPath(value) {
    if (!value) return
    localPath.value = value
    let arr = value.split('/')
    let name = arr[arr.length - 1] || arr[arr.length - 2]
    if (name) {
        pluginName.value = name
    }
}

function propmptFolder() {
    panoptic.showModal(ModalId.FOLDERSELECTION, { callback: setLocalPath })
}

function onNameFocus() {
    if (mode.value == 'github' && pluginName.value == '') {
        const split = gitUrl.value.split('/')
        const repo = split[split.length - 1]
        const name = repo.endsWith('.git') ? repo.slice(0, -4) : repo
        pluginName.value = name
    }
}

async function load() {
    isLoading.value = true
    await nextTick()
    const plugin: PluginAddPayload = { pluginName: pluginName.value }
    if (mode.value == 'github') plugin.gitUrl = gitUrl.value
    if (mode.value == 'local') plugin.path = localPath.value
    await panoptic.addPlugin(plugin)
    isLoading.value = false
    emits('cancel')
}

function setPanopticMl() {
    mode.value = 'github'
    gitUrl.value = 'https://github.com/CERES-Sorbonne/PanopticML'
    pluginName.value = 'PanopticML'
}

</script>

<template>
    <div>
        <div style="font-size: 20px;" class="mb-1">
            <i class="bi bi-github rounded bbb me-1" :class="mode == 'github' ? 'selected' : ''" @click="mode = 'github'" />
            <i class="bi bi-folder rounded bbb me-1" :class="mode == 'local' ? 'selected' : ''"
                @click="mode = 'local'" />
        </div>
        <div v-if="mode == 'github'" class="d-flex">
            <i class="bi bi-github me-2 ms-1" style="font-size: 19px;" />
            <input type="url" v-model="gitUrl" placeholder="Enter git url" style="width: 250px;" />
            <input v-if="showName" v-model="pluginName" type="text" placeholder="plugin unique name"
                style="width: 150px;" class="ms-2" @focus="onNameFocus" />
            <div v-if="showLoad" class="bbb ms-2" @click="load">Load</div>
            <div v-if="isLoading" style="position: relative; top: 7px"
                class="spinner-border spinner-border-sm text-primary ms-1" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
        <div v-if="mode == 'local'" class="d-flex">
            <div class="bbb pe-2 me-2" @click="propmptFolder"><i class="bi bi-folder me-2 ms-1" />Select</div>
            <input type="url" v-model="localPath" placeholder="Folder path" style="width: 200px;" />
            <input v-if="showName" v-model="pluginName" type="text" placeholder="plugin unique name"
                style="width: 150px;" class="ms-2" />
            <div v-if="showLoad" class="bbb ms-2" @click="load">Load</div>
            <div v-if="isLoading" style="position: relative; top: 7px"
                class="spinner-border spinner-border-sm text-primary ms-1" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
        <div class="mt-2 mb-2" :class="helpMessage.includes('.error') ? 'text-danger' : ''">
            {{ $t(helpMessage) }}
        </div>
        <div class="text-warning">{{ $t('main.home.plugins.warning') }}</div>
        <div>
            <div class="bbb mt-2 text-center" style="width: 70px;" @click="emits('cancel')">Cancel</div>
        </div>
    </div>
</template>

<style scoped>
.selected {
    background-color: rgb(227, 227, 255);
}
</style>