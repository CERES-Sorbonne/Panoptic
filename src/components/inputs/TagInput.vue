<script setup lang="ts">
import TagBadge from '../TagTree/TagBadge.vue';

import { ref, computed, onMounted, onUnmounted, reactive } from 'vue'

import { globalStore } from '../../data/store'
import { PropertyRef, Tag } from '@/data/models';
import { isArray } from '@vue/shared';

const props = defineProps({
    property: { type: Object as () => PropertyRef, required: true }
})

const tagInput = ref('');
const showTagList = ref(false);
const tagInputContainer = ref(null);
const tagProposals = ref(null);
const input = ref(null)
const selectedIndex = ref(0)
const inputElem = ref(null)

const tags = computed(() => globalStore.tags[props.property.propertyId])


const filteredTagList = computed(() => {
    if (!props.property.value) {
        props.property.value = []
    }
    let filtered = Object.values(tags.value).filter(tag => !(props.property.value as string[]).includes(tag.value.toLowerCase()) && tag.value.toLowerCase().includes(tagInput.value.toLowerCase()));
    return filtered

})

const isCreatePossible = computed(() => tagInput.value.length > 0 && !filteredTagList.value.some(t => t.value == tagInput.value))

const isCreateSelected = computed(() => selectedIndex.value == filteredTagList.value.length && isCreatePossible.value)
const imageTags = computed(() => {
    let res: string[] = []
    if (props.property.value && isArray(props.property.value)) {
        res.push(...(props.property.value as string[]))
    }
    return res
})
const hasTags = computed(() => imageTags.value.length > 0)
// Ferme la liste de propositions si le clic est effectué en dehors de la liste ou de l'input
const handleContainerClick = (event: any) => {
    if (!(tagProposals.value && tagProposals.value.contains(event.target)) && !tagInputContainer.value.contains(event.target)) {
        showTagList.value = false;
    }
};

const selectOption = async function () {
    if (isCreateSelected.value) {
        await globalStore.addTag(props.property.propertyId, tagInput.value);
        (props.property.value as string[]).push(tagInput.value)
    }
    else if (selectedIndex.value < filteredTagList.value.length) {
        let tagg = filteredTagList.value[selectedIndex.value].value;
        (props.property.value as string[]).push(tagg)
    }
    else {
        return
    }
    tagInput.value = ''
    await globalStore.addOrUpdatePropertyToImage(props.property.imageSHA1, props.property.propertyId, props.property.value)
    inputElem.value.focus()
}

function optionClass(id: number) {
    if (selectedIndex.value == id) {
        return 'bg-selected'
    }
    else {
        return 'bg-white'
    }
}


const deleteTag = async (tag: any) => {
    let index = props.property.value.indexOf(tag)
    props.property.value.splice(index, 1)
    await globalStore.addOrUpdatePropertyToImage(props.property.imageSHA1, props.property.propertyId, props.property.value)
    inputElem.value.focus()
}

function moveSected(value: number) {
    let bonus = isCreatePossible.value ? 0 : -1
    if (value > 0 && selectedIndex.value < filteredTagList.value.length + bonus) {
        selectedIndex.value += 1
    }
    else if (value < 0 && selectedIndex.value > 0) {
        selectedIndex.value -= 1
    }
}

onMounted(() => {
    if(!props.property.value) {
        props.property.value = []
    }
    document.addEventListener('mousedown', handleContainerClick);
});

onUnmounted(() => {
    document.removeEventListener('mousedown', handleContainerClick);
});

</script>

<template>
    <div>
        <div class="tag-input" ref="tagInputContainer" @keydown.down.prevent="moveSected(1)"
            @keydown.up.prevent="moveSected(-1)" @keydown.enter="selectOption">
            <input type="text" v-model="tagInput" placeholder="Add a tag"
                @focus="showTagList = true" style="width: 100%;" @input="selectedIndex = 0" ref="inputElem"/>

            <ul v-if="showTagList" class="tag-proposals bg-white">
                <li v-if="hasTags" class="bg-light m-0 p-0 pb-1 pt-1" style="width: 300px;">
                    <TagBadge @delete="deleteTag(tag)" :show-delete="true" :tag="(tag as string)"
                        v-for="tag in props.property.value" />
                </li>
                <p class="m-0 ms-2 me-2 text-muted text-nowrap" style="font-size: 14px;">Select a tag or create one</p>
                <li @mouseover="selectedIndex = index" @click="selectOption" :class="optionClass(index)" v-for="tag, index in filteredTagList" style="cursor: pointer;"><a class="ms-2" href="#">
                        <TagBadge :tag="tag.value" />
                    </a></li>
                <li @mouseover="selectedIndex = filteredTagList.length" @click="selectOption" v-if="isCreatePossible" :class="optionClass(filteredTagList.length)" style="cursor: pointer;"><span
                        class="text-muted ms-1">Create </span>
                    <TagBadge :tag="tagInput" />
                </li>
            </ul>
        </div>
    </div>
</template>

<style scoped>
.tag-input {
    margin-top: 1rem;
    position: relative;
}

.tag-list {
    display: flex;
    flex-wrap: wrap;
    margin-top: 0.5rem;
}

.tag-list>* {
    margin-right: 0.5rem;
    margin-bottom: 0.5rem;
}

.tag-proposals {
    position: absolute;
    top: 100%;
    left: 0;
    z-index: 10;
    background-color: white;
    border: 1px solid gray;
    border-top: none;
    border-radius: 0 0 0.2rem 0.2rem;
    padding: 0px;
    list-style: none;
    /* max-height: 120px; */
    /* overflow-y: visible; */
}</style>