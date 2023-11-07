<script setup lang="ts">
import { PropertyType, Tag } from '@/data/models';
import { globalStore } from '@/data/store';
import { ref, computed, onMounted, nextTick, watch } from 'vue';
import TagBadge from '../tagtree/TagBadge.vue';

const props = defineProps({
    propertyId: { type: Number, required: true },
    modelValue: Array<number>,
    excluded: Set<number>
})

const emits = defineEmits(['update:modelValue', 'select', 'unselect'])

defineExpose({
    focus
})

const searchElem = ref(null)

const tagFilter = ref('')


const property = computed(() => {
    return globalStore.properties[props.propertyId]
})

const tags = computed(() => globalStore.tags[property.value.id])
const filteredTagList = computed(() => {
    let filtered = Object.values(tags.value).filter((tag: Tag) => tag.value.toLowerCase().includes(tagFilter.value.toLowerCase()))
    if(props.excluded) {
        filtered = filtered.filter(t => !props.excluded.has(t.id))
    }
    return filtered

})

function toggle(tagId: number) {
    if (props.modelValue.includes(tagId)) {
        removeTag(tagId)
        return
    }
    emits('update:modelValue', [...props.modelValue, tagId])
    emits('select', tagId)
}

function removeTag(tagId: number) {
    emits('update:modelValue', props.modelValue.filter(tag => tag != tagId))
    emits('unselect', tagId)
}

function focus() {
    nextTick(() => {
        if (!searchElem.value) return
        searchElem.value.focus()
    })
}

onMounted(() => {
    if (property.value.type != PropertyType.multi_tags && property.value.type != PropertyType.tag) {
        throw 'TagDropdown got propertyId that does not correspond to a tag | multi_tags type..\nGiven type: ' + property.value.type
    }
    // searchElem.value.focus()
    if (!props.modelValue) {
        emits('update:modelValue', [])
    }
})

watch(() => props.modelValue, () => {
    if (!props.modelValue) return
    focus()
})

</script>

<template>
    <ul class="m-0 p-0" v-if="props.modelValue">
        <div class="text-wrap word-break mb-1">
            <span v-for="tagId in props.modelValue">
                <TagBadge class="me-1" :tag="tags[tagId].value" :color="tags[tagId].color" :show-delete="true"
                    @delete="removeTag(tagId)" />
            </span>
        </div>
        <div class="w-100 mb-1"><input type="text" class="w-100" v-model="tagFilter" ref="searchElem"
                style="font-size: 13px;" /></div>
        <div class="list">
            <li v-for="tag in filteredTagList" class="dropdown-item ms-0 ps-1" style="cursor:pointer"
                @click="toggle(tag.id)">
                <input type="checkbox" class="me-2" :checked="props.modelValue.includes(tag.id)" />
                <TagBadge :tag="tag.value" :color="tag.color" />
            </li>
        </div>

    </ul>
</template>

<style scoped>
.list {
    max-height: 400px;
    overflow-y: scroll;
    scrollbar-width: none;
}

.list::-webkit-scrollbar {
  display: none;
}

</style>