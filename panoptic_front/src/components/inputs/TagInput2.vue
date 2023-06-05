<script setup lang="ts">
import { Tag } from '@/data/models'
import { globalStore } from '@/data/store'
import { computed, onMounted, ref } from 'vue'
import TagBadge from '../TagTree/TagBadge.vue'


const props = defineProps({
    propertyId: { type: Number, required: true },
    modelValue: Array<number>,
    focus: Boolean
})

const emits = defineEmits(['update:modelValue'])

const searchElem = ref(null)
const buttonElem = ref(null)

const tagFilter = ref('')


const property = computed(() => {
    return globalStore.properties[props.propertyId]
})

const tags = computed(() => globalStore.tags[property.value.id])
const filteredTagList = computed(() => {
    let filtered = Object.values(tags.value).filter((tag: Tag) => tag.value.toLowerCase().includes(tagFilter.value.toLowerCase()));
    return filtered

})

function toggle(tagId: number) {
    if (props.modelValue.includes(tagId)) {
        removeTag(tagId)
        return
    }
    emits('update:modelValue', [...props.modelValue, tagId])
}

function removeTag(tagId: number) {
    emits('update:modelValue', props.modelValue.filter(tag => tag != tagId))
}

</script>

<template>
    <div v-if="props.modelValue">
        <div class="m-2">
            <span v-for="tagId in props.modelValue">
                <TagBadge :tag="tags[tagId].value" :show-delete="true" @delete="removeTag(tagId)" />
            </span>
        </div>
        <input type="text" class="m-2" v-model="tagFilter" ref="searchElem" />
        <li v-for="tag in filteredTagList" class="dropdown-item" style="cursor:pointer" @click="toggle(tag.id)">
            <input type="checkbox" class="me-2" :checked="props.modelValue.includes(tag.id)" />
            <TagBadge :tag="tag.value" />
        </li>
    </div>
</template>