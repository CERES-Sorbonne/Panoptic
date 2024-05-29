<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import Dropdown from './Dropdown.vue';
import { useProjectStore } from '@/data/projectStore'
import { Tag } from '@/data/models';
import TagInput from '../tags/TagInput.vue';
import { useDataStore } from '@/data/dataStore';

const project = useProjectStore()
const data = useDataStore()

const props = defineProps({
    propertyId: Number,
    tagId: Number
})
const emits = defineEmits(['hide'])

const localChildren = ref([])

const tag = computed(() => data.properties[props.propertyId].tags[props.tagId])
const realChildren = computed(() => tag.value?.children ?? [])
const excluded = computed(() => {
    const res = new Set<number>()

    const recursive = (t: Tag) => {
        if (t == undefined) return
        res.add(t.id)
        t.parents.forEach(p => recursive(data.properties[props.propertyId].tags[p]))
    }
    recursive(tag.value)
    return Array.from(res)
})

function addChild(tag: Tag) {
    project.addTagParent(tag.id, props.tagId)
}

function deleteChild(tagId: number) {
    const childTag = data.properties[props.propertyId].tags[tagId]
    project.deleteTagParent(childTag.id, props.tagId)
}

function updateLocal() {
    localChildren.value.length = 0
    localChildren.value.push(...realChildren.value.map(c => c))
}

onMounted(updateLocal)
watch(realChildren, updateLocal)
</script>

<template>
    <Dropdown @hide="emits('hide')" :auto-focus="false" :teleport="true">
        <template v-slot:button>
            <span class="text-nowrap  sm-btn">
                <i class="bi bi-node-plus me-1" style="position: relative; top: 1.5px;"></i>
                <span style="font-size: 10px;">{{ realChildren.length }}</span>
            </span>
        </template>
        <template v-slot:popup>
            <div class="p-1 main-box">
                <TagInput v-model="localChildren" :property="data.properties[props.propertyId]" :excluded="excluded"
                    @select="addChild" @remove="deleteChild" :auto-focus="true"/>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.main-box {
    padding: 4px;
    width: 250px;
    max-height: 400px;
    overflow-y: scroll;
}
</style>