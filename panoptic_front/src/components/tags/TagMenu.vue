<script setup lang="ts">

/**
 * Menu for tags
 * Used to create, find, select, customize, link and delete tags
 * By default only find and select is allowed
 * 
 */
import { computed, onMounted, ref, watch } from 'vue';
import TagBadge from '../tagtree/TagBadge.vue';
import TagListScroller from './TagListScroller.vue';
import { deletedID, Property, Tag, PropertyType, TagIndex } from '@/data/models';
import { useDataStore, deletedName } from '@/data/dataStore';
import { objValues } from '@/utils/utils';

const data = useDataStore()

const props = defineProps({
    property: Object as () => Property,
    excluded: Array<number>,
    canCreate: Boolean,
    canCustomize: Boolean,
    canLink: Boolean,
    canDelete: Boolean,
    autoFocus: Boolean
})

const emits = defineEmits(['select', 'create', 'delete', 'tab'])

defineExpose({
    focus
})

const searchElem = ref(null)
const listElem = ref(null)

const tagFilter = ref('')


const tagProposals = ref(null);
// undefined = nothing highlighted. The list opens with no row looking hovered; typing or an
// arrow key puts the highlight on the first match.
const selectedIndex = ref(undefined)

const isCreatePossible = computed(() => tagFilter.value.length > 0 && !filteredTagList.value.some(t => t.value == tagFilter.value))

const isCreateSelected = computed(() => selectedIndex.value == filteredTagList.value.length && isCreatePossible.value)

// A deleted tag is not removed from data.tags; the store marks it in place (id -> deletedID,
// value -> deletedName). Exclude both markers so tombstoned / undone tags never appear.
const isDeleted = (t: Tag) => t.id == deletedID || t.value == deletedName || t.deleted
const tags = computed(() => {
    const res: TagIndex = {}
    objValues(data.tags).filter(t => t.propertyId == props.property.id && !isDeleted(t)).forEach(t => res[t.id] = t)
    return res
})
const filteredTagList = computed(() => {
    let filtered = Object.values(tags.value).filter((tag: Tag) => tag.value.toLowerCase().includes(tagFilter.value.toLowerCase()));

    if (props.excluded) {
        filtered = filtered.filter(t => !props.excluded.includes(t.id))
    }

    filtered.sort((t1, t2) => t2.count - t1.count)
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
    scrollToSelected()
}


const selectOption = async function () {
    if (selectedIndex.value == undefined) return

    if (isCreateSelected.value) {
        const newTag = await data.addTag(props.property.id, tagFilter.value, undefined, -1);
        emits('create', newTag)
    }
    else if (selectedIndex.value < filteredTagList.value.length) {
        let selectedTag = filteredTagList.value[selectedIndex.value]
        emits('select', selectedTag)
    }
    tagFilter.value = ''
    focus()
    if (props.property.type == PropertyType.tag) {
        // emits('tab')
    }
}

function scrollToSelected() {
    // The last index can be the "create tag" row, which lives outside the scroller.
    if (selectedIndex.value == undefined || selectedIndex.value >= filteredTagList.value.length) return
    listElem.value?.scrollToIndex(selectedIndex.value)
}

function endSelection(index) {
    if (selectedIndex.value == index) {
        selectedIndex.value = undefined
    }
}

// Searching means the top match is the one Enter should take.
watch(tagFilter, (val) => {
    selectedIndex.value = val.length ? 0 : undefined
})

watch(filteredTagList, () => {
    if (filteredTagList.value.length == 0 && isCreatePossible.value) {
        selectedIndex.value = 0
    }
})

</script>

<template>
    <div class="m-0 p-0">
        <div class="w-100 search-row">
            <input type="text" class="w-100 search" v-model="tagFilter" ref="searchElem"
                style="font-size: 13px; min-width: 100px;" @keydown.down="moveSelected(1)"
                @keydown.up="moveSelected(-1)" @keydown.enter="selectOption" @keydown.escape.capture=""
                @keydown.tab.stop.prevent="emits('tab')" />
        </div>

        <!-- what the list below is for -->
        <div class="list-hint">{{ $t('tag_menu_hint') }}</div>

        <div class="pb-0">
            <TagListScroller ref="listElem" :property="props.property" :tags="filteredTagList"
                v-model:selected-index="selectedIndex" :can-link="props.canLink" :can-customize="props.canCustomize"
                :can-delete="props.canDelete" :max-height="300" @select="index => { selectedIndex = index; selectOption() }"
                @delete="id => emits('delete', id)" @hide="focus" />

            <div v-if="props.canCreate && isCreatePossible" :class="[optionClass(filteredTagList.length), 'tag-row']"
                style="cursor: pointer;" @mouseover="selectedIndex = filteredTagList.length"
                @click.prevent.stop="selectOption">
                <!-- same ms-2 indent as the tag rows above: it is one of them, not a footer -->
                <div class="ms-2 d-flex align-items-center">
                    <span class="text-muted me-1">{{ $t('tag_menu_create') }}</span>
                    <TagBadge :name="tagFilter" :color="-1" />
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
/* No chrome of its own: it sits in whatever surface the host gives it (the tinted selection
   zone in TagInput) and reads as a caret on that surface rather than as a boxed field. */
.search {
    appearance: none;
    border: none;
    outline: none;
    /* no surface of its own: it sits on the host's tint and reads as a caret on it */
    background-color: transparent;
    padding: 2px 0;
    font: inherit;
}

.search-row {
    padding: 4px 8px 6px;
}

/* A row is a badge with room around it, not a line of text: without this the badges stack edge
   to edge and read as one block. The padding is what separates them; the badge itself is then
   centred in the row it sits in. */
.tag-row {
    /* pulled 4px out on each side and given the same back as padding: the row's highlight runs
       wider than its content instead of hugging the badge, while the badge itself does not move */
    margin: 0 -4px;
    padding: 3px 4px;
    border-radius: 3px;
}

.list-hint {
    padding: 6px 8px 2px;
    font-size: 12px;
    color: var(--text-secondary, #6c757d);
}

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