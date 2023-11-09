<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import Dropdown from './Dropdown.vue';
import { globalStore } from '@/data/store';
import { Tag } from '@/data/models';
import TagInput from '../tags/TagInput.vue';


const props = defineProps({
    propertyId: Number,
    tagId: Number
})
const emits = defineEmits(['hide'])

const localChildren = ref([])

const tag = computed(() => globalStore.tagNodes[props.propertyId][props.tagId])
const realChildren = computed(() => tag.value?.children ?? [])
const excluded = computed(() => {
    const res = new Set<number>()

    const recursive = (t: Tag) => {
        if (t == undefined) return
        res.add(t.id)
        t.parents.forEach(p => recursive(globalStore.tags[props.propertyId][p]))
    }
    recursive(tag.value)
    return Array.from(res)
})

function addChild(tag: Tag) {
    // const childTag = globalStore.tags[props.propertyId][tagId]
    globalStore.addTagParent(tag.id, props.tagId)
}

function deleteChild(tagId: number) {
    const childTag = globalStore.tags[props.propertyId][tagId]
    globalStore.deleteTagParent(childTag.id, props.tagId, true)
}

function updateLocal() {
    localChildren.value.length = 0
    localChildren.value.push(...realChildren.value.map(c => c.id))
}

onMounted(updateLocal)
watch(realChildren, updateLocal)
</script>

<template>
    <Dropdown @hide="emits('hide')">
        <template v-slot:button>
            <span class="text-nowrap  sm-btn">
                <i class="bi bi-node-plus me-1" style="position: relative; top: 1.5px;"></i>
                <span style="font-size: 10px;">{{ realChildren.length }}</span>
            </span>
        </template>
        <template v-slot:popup>
            <div class="p-1 main-box">
                <TagInput v-model="localChildren" :property="globalStore.properties[props.propertyId]" :excluded="excluded"
                    @select="addChild" @remove="deleteChild" :auto-focus="true"/>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.main-box {
    padding: 4px;
    width: 250px;
}
</style>