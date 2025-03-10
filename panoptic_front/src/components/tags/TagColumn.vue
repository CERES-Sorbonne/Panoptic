<script setup lang="ts">
import TagOptionsDropdown from '@/components/dropdowns/TagOptionsDropdown.vue';
import TagBadge from '@/components/tagtree/TagBadge.vue';
import { deletedID, useDataStore } from '@/data/dataStore';
import { keyState } from '@/data/keyState';
import { Tag } from '@/data/models';
import { sum } from '@/utils/utils';
import { ref, watch, computed, onMounted } from 'vue'
import draggableComponent from 'vuedraggable';

const data = useDataStore()

const props = defineProps<{
    tags: Tag[],
    title: string,
    main?: boolean,
    selected?: Tag,
    selectedTags?: Tag[],
    draggable?: boolean
    disabled?: boolean
    noCreate?: boolean
}>()
const emits = defineEmits(['select', 'unselect', 'create', 'dragstart', 'dragend', 'added', 'removed'])

const openInput = ref(false)
const inputElem = ref(null)
const filterValue = ref('')

const editTagName = ref(false)
const editTagInput = ref('')
const editTagNameInputElem = ref(null)

const selectedTag = ref(-1)
const tagList = ref<Tag[]>([])

const sortDireciton = ref([1, 1, 1])
const sortMode = ref(0) // 0 alpha, 1 count, 2 color

const lastSelectedTag = ref<Tag>(null)

const filteredTags = computed(() => {
    let tags = []
    if (!filterValue.value) {
        tags = props.tags
    } else {
        const value = filterValue.value.toLocaleLowerCase()
        tags = props.tags.filter(t => t.value.toLocaleLowerCase().includes(value))
    }

    const res: Tag[] = []
    const marked = new Set()
    for (let t of tags) {
        if (marked.has(t.id)) continue
        res.push(t)
        marked.add(t.id)
    }
    const mode = sortMode.value
    const direction = sortDireciton.value[mode]
    if (mode == 0) {
        res.sort((a, b) => a.value.localeCompare(b.value) * direction)
    }
    else if (mode == 1) {
        res.sort((a, b) => (a.count - b.count) * direction)
    }
    return res.filter(t => t.id != deletedID)
})

const filterMatch = computed(() => {
    if (filterValue.value == '') return undefined
    const find = filteredTags.value.find(t => t.value == filterValue.value)
    return find
})


function selectMode(mode: number) {
    if (sortMode.value == mode) {
        sortDireciton.value[mode] *= -1
    } else {
        sortMode.value = mode
    }
}

function inputClose() {
    filterValue.value = ''
    inputElem.value.blur()
    openInput.value = false
}

function inputBlur() {
    inputElem.value.blur()
    if (filterValue.value == '') {
        inputClose()
    }
}

function openSearch() {
    openInput.value = true
}

function selectTag(tag: Tag) {
    const index = props.selectedTags.findIndex(t => t.id == tag.id)
    if(index >= 0) {
        const selected = props.selectedTags
        selected.splice(index, 1)
        emits('select', selected)
    }
    else if(keyState.shift && props.main) {
        multiSelect(tag)
    } else if(keyState.ctrl || (keyState.shift && !props.main)) {
        emits('select', [...props.selectedTags, tag])
    } else {
        emits('select', [tag])
    }
}

function multiSelect(tag: Tag) {
    const lastTag = props.selectedTags.length ? props.selectedTags[props.selectedTags.length-1] : undefined
    const tags = filteredTags.value

    const lastIndex = lastTag ? tags.findIndex(t => t.id == lastTag.id) : undefined
    const index = tags.findIndex(t => t.id == tag.id)

    let toAdd: Tag[] = []
    if(lastIndex >= 0) {
        if(lastIndex < index) {
            toAdd = tags.slice(lastIndex+1, index+1)
        } else {
            toAdd = tags.slice(index, lastIndex)
        }
    } else {
        toAdd = [tag]
    }
    const selectedSet = new Set(props.selectedTags.map(t => t.id))
    toAdd = toAdd.filter(t => !selectedSet.has(t.id))
    emits('select', [...props.selectedTags, ...toAdd])
}

function createTag() {
    emits('create', filterValue.value)
    inputClose()
}

function onDrag(e) {
    const index = e.oldIndex
    const tag = filteredTags.value[index]
    emits('dragstart', tag)
}

function deleteTag(t) {
    emits('removed', t)
}

function tagClass(t: Tag) {
    if (!props.selectedTags) return ''
    if (props.selectedTags.find(tag => tag.id == t.id)) return 'bg-blue'
    if (t.id == selectedTag.value) return 'bg-selected'
    return ''
}

watch(openInput, () => {
    if (openInput.value) {
        inputElem.value.focus()
    }
})

watch(filterValue, () => selectedTag.value = -1)
watch(filteredTags, () => tagList.value = [...filteredTags.value])
onMounted(() => tagList.value = [...filteredTags.value])

</script>

<template>
    <div class="box d-flex flex-column">
        <div class="search d-flex">
            <div class="flex-grow-1"></div>
            <div v-if="!openInput" class="text-nowrap">{{ $t('modals.tags.col_title_' + props.title) }}</div>
            <div class="flex-grow-1">
            </div>
            <div class="search-box d-flex me-1">
                <input ref="inputElem" type="text" class="search-input" style="cursor: pointer;" v-model="filterValue"
                    @keydown.esc.stop="inputClose" @blur="inputBlur" @keydown.enter="createTag"
                    :class="openInput ? 'open-input' : 'closed-input'" />
                <div v-if="filterValue != ''" @click="inputClose" style="cursor: pointer;"><span
                        class="me-1 bi bi-x"></span></div>
                <div v-else class="me-1 bi bi-search" @click="openSearch" style="cursor: pointer;"></div>
                <div @click="selectMode(0)" class="sort-option" style="cursor: pointer;">
                    <i v-if="sortDireciton[0] > 0" class="bi bi-sort-alpha-down"></i>
                    <i v-else class="bi bi-sort-alpha-up-alt"></i>
                    <div v-if="sortMode == 0" class="selected-sort"></div>
                </div>
                <div class="sort-option" @click="selectMode(1)" style="cursor: pointer;">
                    <i v-if="sortDireciton[1] > 0" class="bi bi-sort-down-alt"></i>
                    <i v-else class="bi bi-sort-up"></i>
                    <div v-if="sortMode == 1" class="selected-sort"></div>
                </div>
            </div>
        </div>

        <div v-if="props.main" class="text-center p-2 selected-tag">
            <div v-if="props.selectedTags.length" class="d-flex" style="height: 24px;">
                <div class="flex-grow-1">{{ props.selectedTags.length }} Selected</div>
                <div><i class="bi bi-x bb" @click="emits('unselect')"></i></div>
            </div>
            <div v-else class="text-secondary">{{ $t('modals.tags.click_any') }}</div>
        </div>
        <div v-if="!filterMatch && filterValue && !props.noCreate" class="d-flex ps-2"
            :class="selectedTag == -1 ? 'bg-selected' : ''" style="cursor: pointer;" @click="">
            <div class="me-1">Create Tag</div>
            <div>
                <TagBadge :name="filterValue" :color="-1" />
            </div>
        </div>
        <draggableComponent v-model="tagList"
            :group="{ name: 'tags', pull: props.main ? 'clone' : false, put: !props.main }" item-key="id" :sort="false"
            style="height: 100%; overflow: auto;" @start="onDrag" @end="emits('dragend')" :disabled="props.disabled"
            @add="e => emits('added', tagList[e.newIndex])">
            <template #item="{ element }" #>
                <div class="d-flex ps-2" :class="tagClass(element)" style="cursor: pointer;" @click="e => selectTag(element)"
                    @mouseenter="selectedTag = element.id" @mouseleave="selectedTag = -1">

                    <div class="overflow-hidden">
                        <TagBadge :id="element.id" />
                    </div>
                    <div class="flex-grow-1" style="margin-left: 2px;"></div>
                    <div v-if="selectedTag == element.id" class="d-flex">
                        <div v-if="!props.noCreate"><i class="bi bi-x sb" @click.stop="deleteTag(element)"></i></div>
                        <TagOptionsDropdown :property-id="element.propertyId" :tag-id="element.id"
                            :can-customize="true" />
                    </div>
                    <div class="me-2 text-secondary" style="font-size: 13px;">{{ element.count +
                        sum(element.allChildren.map(c => data.tags[c].count)) }}</div>
                </div>
            </template>
        </draggableComponent>
        <div v-if="props.disabled" class="disable-overlay"></div>
    </div>
</template>

<style scoped>
.box {
    padding: 6px 0px;
    border-right: 1px solid var(--border-color);
    width: 200px;
    /* font-size: 13px; */
    position: relative;
    user-select: none;
}

.disable-overlay {
    background-color: rgba(128, 128, 128, 0.145);
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    right: 0;
}

.search {
    padding-bottom: 4px;
    border-bottom: 1px solid var(--border-color);
}

.search-box {
    border: 1px solid var(--border-color);
    border-radius: 5px;
    overflow: hidden;
    padding: 0 4px;
}

.search-input {
    -webkit-appearance: none !important;
    -moz-appearance: none !important;
    appearance: none !important;
    border: none;
    margin: 0;
    padding: 0;
    /* margin-top: 1px; */
    /* height: 16px; */
    /* line-height: 10px; */
    font-size: 13px;
    color: var(--text-color);
}

.closed-input {
    width: 0px;
}

.open-input {
    width: 125px;
}

.selected-sort {
    position: absolute;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    width: 19px;
    height: 19px;
    top: 2px;
    left: -2px;
}

.sort-option {
    position: relative;
    margin-left: 2px;
}

.selected-tag {
    border-bottom: 1px solid var(--border-color);
}

.bg-blue {
    background-color: rgba(89, 89, 247, 0.309);
}
</style>