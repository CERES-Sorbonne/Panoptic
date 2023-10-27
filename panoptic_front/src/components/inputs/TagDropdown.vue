<script setup lang="ts">
import { PropertyType, Tag } from '@/data/models';
import { globalStore } from '@/data/store';
import { ref, computed, onMounted, nextTick } from 'vue';
import TagBadge from '../tagtree/TagBadge.vue';

const props = defineProps({
    propertyId: { type: Number, required: true },
    modelValue: Array<number>
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


onMounted(() => {
    if (property.value.type != PropertyType.multi_tags && property.value.type != PropertyType.tag) {
        throw 'TagDropdown got propertyId that does not correspond to a tag | multi_tags type..\nGiven type: ' + property.value.type
    }
    buttonElem.value.addEventListener('show.bs.dropdown', () => {
        nextTick(() => searchElem.value.focus())
    })
    if (!props.modelValue) {
        emits('update:modelValue', [])
    }
})

</script>

<template>
        <div class="dropdown m-0 p-0">
            <div class="text-nowrap text-secondary hover-light tag-button m-0 p-0 btn-icon " data-bs-toggle="dropdown"
                data-bs-auto-close="outside" aria-expanded="false" ref="buttonElem" >
                <template v-if="props.modelValue && props.modelValue.length > 0">
                    <span v-for="tagId in props.modelValue">
                        <TagBadge :tag="tags[tagId].value" :color="tags[tagId].color"  class="me-1"/>
                    </span>
                </template>
                <template v-else>
                    Add Tags...
                </template>

            </div>
            <ul class="dropdown-menu m-0 p-0" v-if="props.modelValue">
                <div class="m-2">
                    <span v-for="tagId in props.modelValue">
                        <TagBadge  class="me-1" :tag="tags[tagId].value" :color="tags[tagId].color" :show-delete="true" @delete="removeTag(tagId)" />
                    </span>
                </div>
                <input type="text" class="m-2" v-model="tagFilter" ref="searchElem" />
                <li v-for="tag in filteredTagList" class="dropdown-item" style="cursor:pointer" @click="toggle(tag.id)">
                    <input type="checkbox" class="me-2" :checked="props.modelValue.includes(tag.id)" />
                    <TagBadge :tag="tag.value"  :color="tag.color"/>
                </li>
            </ul>
        </div>
</template>

<style scoped>
.tag-button {
    max-width: 200px;
    overflow: hidden;
}
</style>