<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import Dropdown from './Dropdown.vue';
import TagInputNoDropdown from '../inputs/TagInputNoDropdown.vue';
import { globalStore } from '@/data/store';
import { Tag } from '@/data/models';


const props = defineProps({
    propertyId: Number,
    tagId: Number
})

const localChildren = ref([])

const tag = computed(() => globalStore.tagNodes[props.propertyId][props.tagId])
const realChildren = computed(() => tag.value?.children ?? [])
const excluded = computed(() => {
    const res = new Set<number>()
    
    const recursive = (t: Tag) => {
        if(t == undefined) return
        res.add(t.id)
        t.parents.forEach(p => recursive(globalStore.tags[props.propertyId][p]))
    }
    recursive(tag.value)
    return res
})

function addChild(tagId: number) {
    const childTag = globalStore.tags[props.propertyId][tagId]
    globalStore.addTagParent(childTag.id, props.tagId)
}

function deleteChild(tagId: number) {
    const childTag = globalStore.tags[props.propertyId][tagId]
    globalStore.deleteTagParent(childTag.id, props.tagId, true)
}

onMounted(() => localChildren.value.push(...realChildren.value.map(c => c.id)))
</script>

<template>
    <Dropdown>
        <template v-slot:button>
            <i class="bi bi-node-plus sm-btn"></i>
        </template>
        <template v-slot:popup>
            <div class="p-1 main-box">
                <TagInputNoDropdown v-model="localChildren" :property-id="props.propertyId" :excluded="excluded" @select="addChild" @unselect="deleteChild"/>
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