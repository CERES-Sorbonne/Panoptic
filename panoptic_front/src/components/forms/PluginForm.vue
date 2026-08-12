<script setup lang="ts">
import { ModalId, PluginAddPayload, PluginType } from '@/data/models';
import { usePanopticStore } from '@/data/panopticStore';
import { computed, nextTick, ref } from 'vue';

const panoptic = usePanopticStore()

const emits = defineEmits(['cancel'])

defineExpose({
    setPanopticMl
})

const mode = ref('github')
const gitUrl = ref('')
const localPath = ref('')
const pipPath = ref('')
const pluginName = ref('')
const isLoading = ref(false)

const takenNames = computed(() => panoptic.plugins.map(p => p.id))
const isNameValid = computed(() => {
    if (pluginName.value == '') return false
    if (takenNames.value.includes(pluginName.value)) return false
    return true
})

const showName = computed(() => (mode.value == "github" && gitUrl.value.length > 0) || (mode.value == "local" && localPath.value.length > 0) || (mode.value == "pip"))
const showLoad = computed(() => showName.value && isNameValid.value)
const showWarning = computed(() => pipPath.value !== 'panopticml' || mode.value !== 'pip')

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
    panoptic.showModal(ModalId.FOLDERSELECTION, { callback: setLocalPath, mode: 'images' })
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
    const plugin: PluginAddPayload = { name: pluginName.value , source: "", type: PluginType.LOCAL}
    if (mode.value == 'github'){
        plugin.source = gitUrl.value
        plugin.type = PluginType.GIT
    }
    if (mode.value == 'local'){
        plugin.source = localPath.value
        plugin.type = PluginType.LOCAL
    }
    if (mode.value == 'pip') {
        plugin.source = pipPath.value
        plugin.type = PluginType.PIP
    }
    await panoptic.addPlugin(plugin)
    isLoading.value = false
    emits('cancel')
}

function setPanopticMl() {
    mode.value = PluginType.PIP
    pipPath.value = 'panopticml'
    pluginName.value = 'PanopticML'
}

</script>

<template>
    <div class="plugin-form">
        <div style="font-size: 20px;" class="mb-1">
            <i class="bi bi-github rounded bbb me-1" :class="mode == 'github' ? 'selected' : ''" @click="mode = 'github'" />
            <i class="bi bi-boxes rounded bbb me-1" :class="mode == 'pip' ? 'selected' : ''" @click="mode = 'pip'" />
            <i class="bi bi-folder rounded bbb me-1" :class="mode == 'local' ? 'selected' : ''"
                @click="mode = 'local'" />
        </div>
        <div v-if="mode == 'github'" class="plugin-row">
            <i class="bi bi-github" style="font-size: 19px;" />
            <input type="url" v-model="gitUrl" placeholder="Enter git url" class="input-main" />
            <input v-if="showName" v-model="pluginName" type="text" placeholder="plugin unique name"
                class="input-name" @focus="onNameFocus" />
            <div v-if="showLoad && !isLoading" class="bbb" @click="load">{{ $t('main.home.plugins.install') }}</div>
            <div v-if="isLoading" class="spinner-border spinner-border-sm text-primary" role="status">
                <span class="visually-hidden">{{ $t('main.home.plugins.load') }}</span>
            </div>
        </div>
        <div v-if="mode == 'local'" class="plugin-row">
            <div class="bbb pe-2" style="white-space: nowrap;" @click="propmptFolder"><i class="bi bi-folder me-2 ms-1" />Select</div>
            <input type="url" v-model="localPath" placeholder="Folder path" class="input-main" />
            <input v-if="showName" v-model="pluginName" type="text" placeholder="plugin unique name"
                class="input-name" />
            <div v-if="showLoad && !isLoading" class="bbb" @click="load">{{ $t('main.home.plugins.install') }}</div>
            <div v-if="isLoading" class="spinner-border spinner-border-sm text-primary" role="status">
                <span class="visually-hidden">{{ $t('main.home.plugins.load') }}</span>
            </div>
        </div>
        <div v-if="mode == 'pip'" class="plugin-row">
            <i class="bi bi-boxes" style="font-size: 19px;" />
            <input type="url" v-model="pipPath" placeholder="Enter name of the python package" class="input-main" />
            <input v-if="showName" v-model="pluginName" type="text" placeholder="plugin unique name"
                class="input-name" @focus="onNameFocus" />
            <div v-if="showLoad && !isLoading" class="bbb" @click="load">{{ $t('main.home.plugins.install') }}</div>
            <div v-if="isLoading" class="spinner-border spinner-border-sm text-primary" role="status">
                <span class="visually-hidden">{{ $t('main.home.plugins.load') }}</span>
            </div>
        </div>
        <div class="mt-2 mb-2" :class="helpMessage.includes('.error') ? 'text-danger' : ''">
            {{ $t(helpMessage) }}
        </div>
        <div v-if="showWarning" class="text-warning">{{ $t('main.home.plugins.warning') }}</div>
        <div>
            <div class="bbb mt-2 text-center" style="width: 70px;" @click="emits('cancel')">Cancel</div>
        </div>
    </div>
</template>

<style scoped>
.plugin-form {
    max-width: 100%;
    overflow-x: hidden;
}

/* Inputs shrink and the row wraps, so adding the spinner never widens the form */
.plugin-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    max-width: 100%;
}

.input-main {
    flex: 1 1 200px;
    min-width: 0;
    max-width: 250px;
}

.input-name {
    flex: 1 1 120px;
    min-width: 0;
    max-width: 150px;
}

.selected {
    background-color: rgb(227, 227, 255);
}
</style>