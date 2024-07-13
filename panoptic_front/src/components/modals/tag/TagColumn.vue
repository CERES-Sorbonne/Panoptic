<script setup lang="ts">
import TagBadge from '@/components/tagtree/TagBadge.vue';
import { Tag } from '@/data/models';
import { defineProps, defineEmits, ref, watch, computed } from 'vue'

const props = defineProps<{
    tags: Tag[],
    title: string,
    main?: boolean,
    selected?: Tag
}>()
const emits = defineEmits(['select', 'unselect'])

const openInput = ref(false)
const inputElem = ref(null)

const sortDireciton = ref([1, 1, 1])
const sortMode = ref(0) // 0 alpha, 1 count, 2 color


function selectMode(mode: number) {
    if (sortMode.value == mode) {
        sortDireciton.value[mode] *= -1
    } else {
        sortMode.value = mode
    }
}

watch(openInput, () => {
    if (openInput.value) {
        inputElem.value.focus()
    }
})

</script>

<template>
    <div class="box d-flex flex-column">
        <div class="search d-flex">
            <div class="flex-grow-1"></div>
            <div class="text-nowrap">{{ props.title }}</div>
            <div class="flex-grow-1">
            </div>
            <div class="search-box d-flex">
                <input ref="inputElem" type="text" class="search-input" @keydown.esc.stop="inputElem.blur()"
                    @blur="openInput = false" :class="openInput ? 'open-input' : 'closed-input'" />
                <div class="me-1 bi bi-search" @click="openInput = true"></div>
                <div @click="selectMode(0)" class="sort-option">
                    <i v-if="sortDireciton[0] > 0" class="bi bi-sort-alpha-down"></i>
                    <i v-else class="bi bi-sort-alpha-up-alt"></i>
                    <div v-if="sortMode == 0" class="selected-sort"></div>
                </div>
                <div class="sort-option" @click="selectMode(1)">
                    <i v-if="sortDireciton[1] > 0" class="bi bi-sort-down-alt"></i>
                    <i v-else class="bi bi-sort-up"></i>
                    <div v-if="sortMode == 1" class="selected-sort"></div>
                </div>
            </div>
        </div>

        <div v-if="props.main" class="text-center p-2 selected-tag">
            <div v-if="props.selected" class="d-flex">
                <div class="flex-grow-1 text-center"><TagBadge :id="props.selected.id" style="font-size: 17px;"/></div>
                <div class="me-2 text-secondary">{{ props.selected.count }}</div>
                <div><i class="bi bi-x bb" @click="emits('unselect')"></i></div>
            </div>
            <div v-else class="text-secondary"> Select any tag...</div>
        </div>

        <div style="overflow: auto;">
            <div v-for="tag in props.tags" class="d-flex">
                <div>
                    <TagBadge :id="tag.id" @click="emits('select', tag.id)" style="cursor: pointer;"/>
                </div>
                <div class="flex-grow-1"></div>
                <div class="me-2 text-secondary" style="font-size: 13px;">{{ tag.count }}</div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.box {
    padding: 6px 8px;
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