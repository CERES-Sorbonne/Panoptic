<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import Dropdown from './Dropdown.vue';
import { useDataStore } from '@/data/dataStore';
import ColorInput from '../property_inputs/ColorInput.vue';
const data = useDataStore()

const props = defineProps({
    propertyId: Number,
    tagId: Number,
    canCustomize: Boolean,
    canDelete: Boolean,
})
const emits = defineEmits(['delete', 'hide'])

const dropdown = ref(null)
const localName = ref('')
const localColor = ref(null)

const nameInput = ref(null)
const visible = ref(false)
const tag = computed(() => data.properties[props.propertyId].tags[props.tagId])


async function updateFromStore() {
    if(!tag.value) return
    localName.value = tag.value.value
    localColor.value = tag.value.color
    await nextTick()
    if (nameInput.value) {
        nameInput.value.focus()
    }
}

function setColor(color: number) {
    data.updateTag(props.tagId, undefined, Number(color))
    dropdown.value.hide()
}

function setName(name: string) {
    if(name == tag.value.value) return
    console.log('set')
    data.updateTag(props.tagId, name)
}

function deleteTag() {
    data.deleteTag(props.tagId)
    emits('delete', props.tagId)
    dropdown.value.hide()
    
}

function onShow() {
    visible.value = true
    updateFromStore()
}

function onHide() {
    if(!visible.value) return
    visible.value = false
    setName(localName.value)
    emits('hide')
}

onMounted(updateFromStore)
watch(() => props.tagId, updateFromStore)


</script>

<template>
    <Dropdown ref="dropdown" @show="onShow" @hide="onHide" :teleport="false">
        <template v-slot:button>
            <span class="pe-1"><i class="bi bi-three-dots sm-btn"  style="position: relative; top: 1.5px;"/></span>
        </template>

        <template v-slot:popup>
            <div class="main-box pt-1">
                <div class="ps-1 pe-1">
                    <input v-if="props.canCustomize" v-model="localName" ref="nameInput" class="w-100 mb-2" @change="setName(localName)" />
                    <div v-if="props.canDelete" class="mb-1 base-btn" @click="deleteTag"><i class="bi bi-trash" /> Delete Tag</div>
                </div>
                <div class="hr w-100" />
                <div v-if="props.canCustomize" class="mt-1" style="height: 317px;">
                    <ColorInput  :hide-preview="true" :hide-white="true" :model-value="localColor" @update:model-value="setColor"/>
                </div>
            </div>
        </template>

    </Dropdown>
</template>

<style scoped>
.main-box {
    width: 200px;
}
</style>