<script setup lang="ts">
import TagBadge from '@/components/tagtree/TagBadge.vue';
import { Tag } from '@/data/models';
import { defineProps, defineEmits, ref, watch, computed, onMounted } from 'vue'
import draggableComponent from 'vuedraggable';

const props = defineProps<{
    tags: Tag[],
    title: string,
    main?: boolean,
    selected?: Tag,
    draggable?: boolean
}>()
const emits = defineEmits(['select', 'unselect', 'create', 'dragstart', 'dragend', 'added', 'removed'])

const openInput = ref(false)
const inputElem = ref(null)
const filterValue = ref('')

const selectedTag = ref(-1)
const tagList = ref<Tag[]>([])

const sortDireciton = ref([1, 1, 1])
const sortMode = ref(0) // 0 alpha, 1 count, 2 color

const filteredTags = computed(() => {
    if (!filterValue.value) return props.tags
    const value = filterValue.value.toLocaleLowerCase()
    return props.tags.filter(t => t.value.toLocaleLowerCase().includes(value))
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

function onUp() {
    if (selectedTag.value == -1) return
    const index = filteredTags.value.findIndex(t => selectedTag.value)
    if (index == 0 || index == -1) return -1
    selectedTag.value = filteredTags.value[index - 1].id
}

function onDown() {
    const tags = filteredTags.value
    const index = tags.findIndex(t => selectedTag.value)
    if (index == tags.length - 1) return
    selectedTag.value = tags[index + 1].id
}

function openSearch() {
    openInput.value = true
}

function selectTag() {
    if (selectedTag.value == -1 && !filterMatch.value) {
        emits('create', { name: filterValue.value, parent })
        return
    }
    if (selectedTag.value > 0) {
        emits('select', filteredTags.value[selectedTag.value].id)
    }
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
            <div class="text-nowrap">{{ props.title }}</div>
            <div class="flex-grow-1">
            </div>
            <div class="search-box d-flex me-1">
                <input ref="inputElem" type="text" class="search-input" style="cursor: pointer;" v-model="filterValue"
                    @keydown.esc.stop="inputClose" @blur="inputBlur" @keydown.down="onDown" @keydown.up="onUp"
                    @keydown.enter="selectTag" :class="openInput ? 'open-input' : 'closed-input'" />
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
            <div v-if="props.selected" class="d-flex">
                <div class="flex-grow-1 text-center">
                    <TagBadge :id="props.selected.id" style="font-size: 17px;" />
                </div>
                <div class="me-2 text-secondary">{{ props.selected.count }}</div>
                <div><i class="bi bi-x bb" @click="emits('unselect')"></i></div>
            </div>
            <div v-else class="text-secondary"> Select any tag...</div>
        </div>
        <div v-if="!filterMatch && filterValue" class="d-flex ps-2" :class="selectedTag == -1 ? 'bg-selected' : ''">
            <div class="me-1">Create Tag</div>
            <div>
                <TagBadge :name="filterValue" :color="-1" />
            </div>
        </div>
        <draggableComponent v-model="tagList" :group="{ name: 'tags', pull: props.main?'clone':false, put: !props.main }" item-key="id" :sort="false" style="min-height: 200px; overflow: auto;"
        @start="emits('dragstart')" @end="emits('dragend')" @add="e => emits('added', tagList[e.newIndex])">
            <template #item="{ element }" #>
                <div class="d-flex ps-2" :class="selectedTag == element.id ? 'bg-selected' : ''" style="cursor: pointer;"
                    @click="emits('select', element.id)" @mouseenter="selectedTag = element.id" @mouseleave="selectedTag = -1">
                    <div>
                        <TagBadge :id="element.id" />
                    </div>
                    <div class="flex-grow-1"></div>
                    <div class="me-2 text-secondary" style="font-size: 13px;">{{ element.count }}</div>
                </div>
            </template>
        </draggableComponent>




        <!-- <div style="overflow: auto;">
            <div v-for="tag, index in filteredTags" class="d-flex ps-2"
                :class="selectedTag == index ? 'bg-selected' : ''" style="cursor: pointer;"
                @click="emits('select', tag.id)" @mouseenter="selectedTag = index" @mouseleave="selectedTag = -1">
                <div>
                    <TagBadge :id="tag.id" />
                </div>
                <div class="flex-grow-1"></div>
                <div class="me-2 text-secondary" style="font-size: 13px;">{{ tag.count }}</div>
            </div>
        </div> -->
    </div>
</template>

<style scoped>
.box {
    padding: 6px 0px;
    border-right: 1px solid var(--border-color);
    width: 250px;
    /* font-size: 13px; */
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
    width: 70px;
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
</style>