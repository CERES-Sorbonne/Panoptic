<script setup lang="ts">

/**
 * Menu for tags
 * Used to create, find, select, customize, link and delete tags
 * By default only find and select is allowed
 * 
 */
import { computed, onMounted, ref, watch } from 'vue';
import TagBadge from '../tagtree/TagBadge.vue';
import TagOptionsDropdown from '../dropdowns/TagOptionsDropdown.vue';
import TagChildSelectDropdown from '../dropdowns/TagChildSelectDropdown.vue';
import { Property, Tag, PropertyType } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';

const project = useProjectStore()

const props = defineProps({
    property: Object as () => Property,
    excluded: Array<number>,
    canCreate: Boolean,
    canCustomize: Boolean,
    canLink: Boolean,
    canDelete: Boolean,
    autoFocus: Boolean
})

const emits = defineEmits(['select', 'create', 'delete'])

defineExpose({
    focus
})

const searchElem = ref(null)

const tagFilter = ref('')


const tagProposals = ref(null);
const selectedIndex = ref(0)

const isCreatePossible = computed(() => tagFilter.value.length > 0 && !filteredTagList.value.some(t => t.value == tagFilter.value))

const isCreateSelected = computed(() => selectedIndex.value == filteredTagList.value.length && isCreatePossible.value)

const tags = computed(() => props.property.tags ?? {})
const filteredTagList = computed(() => {
    let filtered = Object.values(tags.value).filter((tag: Tag) => tag.value.toLowerCase().includes(tagFilter.value.toLowerCase()));

    if (props.excluded) {
        filtered = filtered.filter(t => !props.excluded.includes(t.id))
    }

    filtered.sort((t1, t2) => t2.count - t1.count)
    filtered = filtered.filter(t => !t.deleted)
    return filtered
})

async function focus() {
    if (!searchElem.value) return
    searchElem.value.focus()
}

onMounted(() => {
    if (props.property.type != PropertyType.multi_tags && props.property.type != PropertyType.tag) {
        throw 'TagDropdown got propertyId that does not correspond to a tag | multi_tags type..\nGiven type: ' + props.property.type
    }
    if (props.autoFocus) {
        focus()
    }
})

const optionClass = (id: number) => {
    let bg = selectedIndex.value == id ? 'bg-selected' : 'bg-white'
    return bg
}

const removeTag = async (tag: Tag) => {
};


function moveSelected(value: number) {
    if (selectedIndex.value == undefined) {
        selectedIndex.value = 0
        return
    }
    let bonus = isCreatePossible.value ? 0 : -1
    if (value > 0 && selectedIndex.value < filteredTagList.value.length + bonus) {
        selectedIndex.value += 1
    }
    else if (value < 0 && selectedIndex.value > 0) {
        selectedIndex.value -= 1
    }
}


const selectOption = async function () {
    if (selectedIndex.value == undefined) return

    if (isCreateSelected.value) {
        const newTag = await project.addTag(props.property.id, tagFilter.value);
        emits('create', newTag)
    }
    else if (selectedIndex.value < filteredTagList.value.length) {
        let selectedTag = filteredTagList.value[selectedIndex.value]
        emits('select', selectedTag)
    }
    tagFilter.value = ''
    focus()
}

function endSelection(index) {
    if (selectedIndex.value == index) {
        selectedIndex.value = undefined
    }
}

watch(filteredTagList, () => {
    if (filteredTagList.value.length == 0 && isCreatePossible.value) {
        selectedIndex.value = 0
    }
})

</script>

<template>
    <div class="m-0 p-0">
        <div class="w-100 mb-1">
            <input type="text" class="w-100" v-model="tagFilter" ref="searchElem" style="font-size: 13px; min-width: 100px;"
                @keydown.down="moveSelected(1)" @keydown.up="moveSelected(-1)" @keydown.enter="selectOption" @keydown.escape.capture=""/>
        </div>

        <div class="pb-0" style="max-height: 300px; overflow-y: auto;">
            <div v-for="tag, index in filteredTagList" :class="optionClass(index)" style="cursor: pointer;"
                @mouseover="selectedIndex = index" @mouseleave="endSelection(index)">
                <div class="ms-2 d-flex">
                    <div class="flex-grow-1" style="overflow: hidden;" @click="selectOption">
                        <TagBadge :tag="tag.value" :color="tag.color" />
                    </div>
                    <div v-if="props.canLink" :style="{ color: (selectedIndex == index) ? 'var(--text-color)' : 'white' }">
                        <TagChildSelectDropdown :property-id="tag.propertyId" :tag-id="tag.id" @hide="focus" />
                    </div>
                    <div v-if="props.canCustomize || props.canDelete"
                        :style="{ color: (selectedIndex == index) ? 'var(--text-color)' : 'white' }">

                        <TagOptionsDropdown :property-id="property.id" :tag-id="tag.id" :can-delete="props.canDelete"
                            :can-customize="props.canCustomize" @delete="id => emits('delete', id)" @hide="focus" />
                    </div>
                    <div class="text-secondary" style="font-size: 10px; line-height: 20px; padding-right: 2px;">
                        {{ tag.count }}
                    </div>

                </div>
            </div>
            <div v-if="props.canCreate && isCreatePossible" :class="optionClass(filteredTagList.length)"
                style="cursor: pointer;" @mouseover="selectedIndex = filteredTagList.length"
                @click.prevent.stop="selectOption">
                <span class="text-muted ms-1">Create </span>
                <TagBadge :tag="tagFilter" :color="-1" />
            </div>
        </div>
    </div>
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

li {
    padding: 2px 0px;
    border-radius: 3px;

}
</style>