<script setup lang="ts">
import { ModalId, PluginAddPayload } from '@/data/models';
import { usePanopticStore } from '@/data/panopticStore';
import { useProjectStore } from '@/data/projectStore';
import { computed, ref } from 'vue';

const panoptic = usePanopticStore()

const emits = defineEmits(['cancel'])

const mode = ref('local')
const gitUrl = ref('')
const localPath = ref('')
const pluginName = ref('')

const takenNames = computed(() => panoptic.data.plugins.map(p => p.name))
const isNameValid = computed(() => {
    if (pluginName.value == '') return false
    if (takenNames.value.includes(pluginName.value)) return false
    return true
})

const showName = computed(() => (mode.value == "github" && gitUrl.value.length > 0) || (mode.value == "local" && localPath.value.length > 0))
const showLoad = computed(() => showName.value && isNameValid.value)

const helpMessage = computed(() => {
    if(showName.value && takenNames.value.includes(pluginName.value)) {
        return 'Error: plugin name is already used'
    }
    if(showName.value) {
        return 'Select unique plugin name'
    }
    if(mode.value == 'github') {
        return 'Github path is required'
    }
    return 'Select a folder'
})

function setLocalPath(value) {
    if(!value) return
    localPath.value = value
    let arr = value.split('/')
    let name = arr[arr.length-1] || arr[arr.length-2]
    if(name) {
        pluginName.value = name
    }
}

function propmptFolder() {
    panoptic.showModal(ModalId.FOLDERSELECTION, { callback: setLocalPath })
}

async function load() {
    const plugin:PluginAddPayload = {pluginName: pluginName.value}
    if (mode.value == 'github') plugin.gitUrl = gitUrl.value
    if (mode.value == 'local') plugin.path = localPath.value
    await panoptic.addPlugin(plugin)
    emits('cancel')
}
</script>

<template>
    <div>
        <div style="font-size: 20px;" class="mb-1">
            <i class="bi bi-folder rounded bbb me-1" :class="mode == 'local' ? 'selected': ''" @click="mode = 'local'"/>
            <i class="bi bi-github rounded bbb" :class="mode == 'github' ? 'selected': ''" @click="mode = 'github'"/>
        </div>
        <div v-if="mode == 'github'" class="d-flex">
            <i class="bi bi-github me-2" style="font-size: 19px;" />
            <input type="url" v-model="gitUrl" placeholder="Enter git url" style="width: 250px;" />
            <input v-if="showName" v-model="pluginName" type="text" placeholder="plugin unique name"
                style="width: 150px;" class="ms-2" />
            <div v-if="showLoad" class="bbb ms-2" @click="load">Load</div>
        </div>
        <div v-if="mode == 'local'" class="d-flex">
            <div class="bbb pe-2 me-2" @click="propmptFolder"><i class="bi bi-folder me-2 ms-1" />Select</div>
            <input type="url" v-model="localPath" placeholder="Folder path" style="width: 200px;" />
            <input v-if="showName" v-model="pluginName" type="text" placeholder="plugin unique name"
                style="width: 150px;" class="ms-2" />
            <div v-if="showLoad" class="bbb ms-2" @click="load">Load</div>
        </div>
        <div class="mt-2 mb-2" :class="helpMessage.startsWith('Error') ? 'text-danger': ''">
            {{ helpMessage }}
        </div>
        <div @click="emits('cancel')">
            <div class="bbb mt-2 text-center" style="width: 70px;">Cancel</div>
        </div>
    </div>
</template>

<style scoped>

.selected {
    background-color: rgb(227, 227, 255);
}

</style>