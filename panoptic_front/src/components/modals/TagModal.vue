<script setup lang="ts">
import { computed, ref } from 'vue'
import Modal2 from './Modal2.vue';
import { ModalId } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import { useDataStore } from '@/data/dataStore';
import { isTag } from '@/utils/utils';
import { usePanopticStore } from '@/data/panopticStore';

const panoptic = usePanopticStore()
const data = useDataStore()

// const props = defineProps<{}>()
// const emits = defineEmits([])
const propId = ref(-1)
const tagId = ref(-1)

const property = computed(() => {
    if(propId.value == -1 || !data.properties[propId.value]) {
        return undefined
    }
    const prop = data.properties[propId.value]
    if(!isTag(prop.type)) {
        return undefined
    }
    return prop
})

const tag = computed(() => {
    if(tagId.value != -1 || !data.tags[tagId.value]) return
    const tag = data.tags[tagId.value]
    if(property.value.id != tag.propertyId) return
    return tag
})

function show() {
    const init = panoptic.modalData
    if(init.propId != undefined) {
        propId.value = init.propId
    }
    if(init.tagId != undefined) {
        tagId.value = init.tagId
    }
}

function hide() {
    propId.value = -1
    tagId.value = -1
}
</script>

<template>
    <Modal2 :id="ModalId.TAG" @show="show" @hide="hide">
        <template #title>Tag</template>
        <template #content="{ data }">
            <div class="h-100 bg-info">
                <div class="d-flex h-100">
                    {{ property }}
                    {{ tag }}
                </div>
            </div>
        </template>
    </Modal2>
</template>

<style scoped>
</style>