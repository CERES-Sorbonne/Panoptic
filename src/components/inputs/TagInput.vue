<script setup lang="ts">
// import TagBadge from '../tagtree/TagBadge.vue';

import { ref, computed, onMounted, onUnmounted, reactive, nextTick } from 'vue'

import { globalStore } from '../../data/store'
import { PropertyRef, Tag } from '@/data/models';
import TagBadge from '../TagTree/TagBadge.vue';
import PropertyIcon from '../properties/PropertyIcon.vue';

console.log("test")

// contains the tag property of this image
const props = defineProps({
    property: { type: Object as () => PropertyRef, required: true },
    maxSize: String,
    monoTag: Boolean
})

const edit = ref(false)


const tagInput = ref('');
const showTagList = ref(false);
const tagInputContainer = ref(null);
const tagProposals = ref(null);
const selectedIndex = ref(0)
const inputElem = ref(null)

const tags = computed(() => globalStore.tags[props.property.propertyId])


const filteredTagList = computed(() => {
    // filter tags according to inputed text
    if (!props.property.value) {
        props.property.value = []
    }
    let filtered = Object.values(tags.value).filter((tag: Tag) => !props.property.value.includes(tag.id) && tag.value.toLowerCase().includes(tagInput.value.toLowerCase()));
    return filtered

})

const isCreatePossible = computed(() => tagInput.value.length > 0 && !filteredTagList.value.some(t => t.value == tagInput.value))

const isCreateSelected = computed(() => selectedIndex.value == filteredTagList.value.length && isCreatePossible.value)

const imageTags = computed(() => props.property.value.map((id: number) => tags.value[id]))

// Ferme la liste de propositions si le clic est effectué en dehors de la liste ou de l'input
const handleContainerClick = (event: any) => {
    if (!edit.value) {
        return
    }
    if (!(tagProposals.value && tagProposals.value.contains(event.target)) && !tagInputContainer.value.contains(event.target)) {
        showTagList.value = false;
        edit.value = false;
    }
};

const selectOption = async function () {
    let valueToAdd: number
    // should we create the tag first ? 
    if (isCreateSelected.value) {
        const newTag = await globalStore.addTag(props.property.propertyId, tagInput.value);
        valueToAdd = newTag.id
    }
    else if (selectedIndex.value < filteredTagList.value.length) {
        let selectedTag = filteredTagList.value[selectedIndex.value]
        if (imageTags.value.indexOf(selectedTag) === -1) {
            valueToAdd = selectedTag.id;
        }
    }
    if (!valueToAdd) {
        return
    }
    tagInput.value = ''
    let updatedValue = props.monoTag ? [valueToAdd] : [...props.property.value, valueToAdd]
    await globalStore.addOrUpdatePropertyToImage(props.property.imageSHA1, props.property.propertyId, updatedValue)
    inputElem.value.focus()
}

const optionClass = (id: number) => selectedIndex.value == id ? 'bg-selected' : 'bg-white'

function setEdit(value: Boolean) {
    if (value) {
        edit.value = true
        nextTick(() => {
            if (!inputElem.value) {
                return
            }
            inputElem.value.focus()
        })
    }
    else {
        globalStore.addOrUpdatePropertyToImage(props.property.imageSHA1, props.property.propertyId, props.property.value)
        edit.value = false
        if (props.property.value == '') {
            props.property.value = undefined
        }
    }
}


const deleteTag = async (tag: any) => {
    let index = props.property.value.indexOf(tag)
    props.property.value.splice(index, 1)
    await globalStore.addOrUpdatePropertyToImage(props.property.imageSHA1, props.property.propertyId, props.property.value)
}

const removeTag = async (tag: Tag) => {
    await globalStore.addOrUpdatePropertyToImage(props.property.imageSHA1,
        props.property.propertyId,
        props.property.value.filter((id: number) => id !== tag.id));
    inputElem.value.focus()
};


function moveSelected(value: number) {
    let bonus = isCreatePossible.value ? 0 : -1
    if (value > 0 && selectedIndex.value < filteredTagList.value.length + bonus) {
        selectedIndex.value += 1
    }
    else if (value < 0 && selectedIndex.value > 0) {
        selectedIndex.value -= 1
    }
}

onMounted(() => {
    if (!props.property.value) {
        props.property.value = []
    }
    document.addEventListener('mousedown', handleContainerClick);
});

onUnmounted(() => {
    document.removeEventListener('mousedown', handleContainerClick);
});

</script>

<template>
    <div class="input-group bg-light">
        <div v-if="!edit" @click="setEdit(true)"  class="input-group-text small bg-light text-dark me-1 overflow-hidden" :style="'width:'+props.maxSize+'px;'">
            <PropertyIcon :type="props.property.type" class="me-1"/>
            <span v-if="!props.property.value || props.property.value.length < 1" class="text-secondary">None</span>
            <span v-else>
                <span v-for="tag in props.property.value">
                    <template
                        v-if="globalStore.tags[props.property.propertyId] && globalStore.tags[props.property.propertyId][tag]">
                        <TagBadge :tag="globalStore.tags[props.property.propertyId][tag].value" />
                    </template>
                </span>
            </span>
            <!-- <span class="text-wrap">{{ props.property }}</span> -->
        </div>
        <div v-else class="tag-input" ref="tagInputContainer" @keydown.down.prevent="moveSelected(1)"
            @keydown.up.prevent="moveSelected(-1)" @keydown.enter="selectOption"
            @keydown.escape.prevent="edit = false">
            <input type="text" v-model="tagInput" placeholder="Add a tag" @focus="showTagList = true" style="width: 100%;"
                @input="selectedIndex = 0" ref="inputElem" class="form-control small"/>

            <ul v-if="showTagList" class="tag-proposals bg-white">
                <li v-if="imageTags" class="bg-light m-0 p-0 pb-1 pt-1" style="width: 300px;">
                    <TagBadge @delete="removeTag(tag)" :show-delete="true" :tag="tag.value" v-for="tag in imageTags" />
                </li>
                <p class="m-0 ms-2 me-2 text-muted text-nowrap" style="font-size: 14px;">Select a tag or create one</p>
                <li @mouseover="selectedIndex = index" @click="selectOption" :class="optionClass(index)"
                    v-for="tag, index in filteredTagList" style="cursor: pointer;"><a class="ms-2" href="#">
                        <TagBadge :tag="tag.value" />
                    </a></li>
                <li @mouseover="selectedIndex = filteredTagList.length" @click="selectOption" v-if="isCreatePossible"
                    :class="optionClass(filteredTagList.length)" style="cursor: pointer;"><span
                        class="text-muted ms-1">Create </span>
                    <TagBadge :tag="tagInput" />
                </li>
            </ul>
        </div>
    </div>
</template>

<style scoped>
.tag-input {
    /* margin-top: 1rem; */
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
}
</style>