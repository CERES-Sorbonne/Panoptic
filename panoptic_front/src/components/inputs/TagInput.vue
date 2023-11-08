<script setup lang="ts">

import { ref, computed, onMounted, onUnmounted, reactive, nextTick, watch } from 'vue'

import { globalStore } from '../../data/store'
import { PropertyRef, Tag } from '@/data/models';
import TagBadge from '../tagtree/TagBadge.vue';
import PropertyIcon from '../properties/PropertyIcon.vue';
import * as boostrap from 'bootstrap'
import * as inputTree from '@/utils/inputTree'

// contains the tag property of this image
const props = defineProps({
    property: { type: Object as () => PropertyRef, required: true },
    maxSize: String,
    monoTag: Boolean,
    inputId: Array<number>,
})

const edit = ref(false)

const localValue = reactive([])
const tagInput = ref('');
const showTagList = ref(false);
const tagInputContainer = ref(null);
const tagProposals = ref(null);
const selectedIndex = ref(0)
const inputElem = ref(null)
const dropdownElem = ref(null)
const clickableElem = ref(null)

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

const imageTags = computed(() => localValue.map((id: number) => tags.value[id]))

// Ferme la liste de propositions si le clic est effectué en dehors de la liste ou de l'input
const handleContainerClick = (event: any) => {
    if (!edit.value) {
        return
    }
    if (!(tagProposals.value && tagProposals.value.contains(event.target)) && !tagInputContainer.value.contains(event.target) && !inputElem.value.contains(event.target)) {
        setEdit(false)
        if (!elemIsInput(event.target, 10)) {
            event.stopPropagation()
        }
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
    localValue.push(valueToAdd)
    // let updatedValue = props.monoTag ? [valueToAdd] : [...props.property.value, valueToAdd]
    // await globalStore.addOrUpdatePropertyToImage(props.property.imageId, props.property.propertyId, updatedValue)
    inputElem.value.focus()
}

const optionClass = (id: number) => {
    let bg = selectedIndex.value == id ? 'bg-selected' : 'bg-white'
    let rounded = id == filteredTagList.value.length - 1 && !isCreatePossible.value ? ' rounded-bottom' : ''
    return bg + rounded
}

function setEdit(value: Boolean) {
    console.log('set edit: ' + value)
    if (value == edit.value) {
        console.log('set edit: double')
        return
    }
    if (value) {
        edit.value = true
        document.addEventListener('click', handleContainerClick, true)
        nextTick(() => {
            console.log(inputElem.value)
            if (!inputElem.value) {
                return
            }
            inputElem.value.focus()
            let dropdown = boostrap.Dropdown.getOrCreateInstance(dropdownElem.value)
            dropdown.show()
        })
    }
    else {
        document.removeEventListener('click', handleContainerClick, true)
        let img = globalStore.images[props.property.imageId]
        if(tagsChanged()) {
            globalStore.setPropertyValue(props.property.propertyId, img, localValue)
        }
        edit.value = false
        showTagList.value = false;
        if (props.property.value == '') {
            props.property.value = undefined
        }
        inputElem.value.focus()
        let dropdown = boostrap.Dropdown.getOrCreateInstance(dropdownElem.value)
        dropdown.hide()
    }
}

function tagsChanged() {
    let oldTags = props.property.value

    if (oldTags.length != localValue.length) {
        return true
    }

    let set = new Set(localValue)
    for(let t of oldTags) 
    {
        if(!set.has(t)) {
            return true
        }
    }

    return false
    
}

function elemIsInput(elem: HTMLElement, depth: number = 0): Boolean {
    if (elem.getAttribute('is-input')) {
        return true
    }
    if (depth > 0 && elem.parentElement) {
        return elemIsInput(elem.parentElement, depth - 1)
    }
    return false
}

const removeTag = async (tag: Tag) => {
    let toDel = localValue.indexOf(tag.id)
    if(toDel >= 0) {
        localValue.splice(toDel, 1)
    }
    // await globalStore.addOrUpdatePropertyToImage(props.property.imageId,
    //     props.property.propertyId,
    //     props.property.value.filter((id: number) => id !== tag.id));
    if (inputElem.value) {
        inputElem.value.focus()
    }
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

function hanldeInputEvent(e: any) {
    e.preventDefault()
    setEdit(true)

}

function loadDbValue() {
    localValue.length = 0
    if(Array.isArray(props.property.value)) {
        localValue.push(...props.property.value)
    }
}

onMounted(() => {
    loadDbValue()
    if (props.inputId) {
        inputTree.registerInput(props.inputId, clickableElem.value)
    }
});

watch(() => props.property, loadDbValue)

watch(() => props.inputId, () => inputTree.registerInput(props.inputId, clickableElem.value), { deep: true, immediate: true })

</script>

<template>
    <div class="pt-1 pb-1 pe-1 input-container" is-input="true">
        <div class="dropdown" @click="setEdit(true)" ref="clickableElem">
            <div class="no-border p-0 text-secondary text-nowrap" type="button" ref="dropdownElem" data-bs-offset="20,0"
                data-ds-toggle="dropdown" data-bs-display="static">
                <div v-if="!edit" class="overflow-hidden" :class="!edit ? 'test-wraped' : ''">
                    <span class="me-1">
                        <PropertyIcon :type="props.property.type" />
                    </span>
                    <span v-if="!edit">
                        <span v-for="tag in imageTags">
                            <TagBadge :tag="tag.value" :color="tag.color" class="me-1"/>
                        </span>
                        <span v-if="imageTags.length == 0">None</span>
                    </span>
                </div>

                <div v-else>
                    <div class="d-flex flex-row">
                        <span class="me-2">
                            <PropertyIcon :type="props.property.type" />
                        </span>
                        <div class="w-100">
                            <input class="m-0 me-1 ps-1 no-border bg-light small-input" ref="inputElem" v-model="tagInput"
                                @keydown.down.prevent="moveSelected(1)" @keydown.up.prevent="moveSelected(-1)"
                                @keydown.enter="selectOption" @keydown.escape.prevent.stop="setEdit(false)"
                                @keydown.shift.tab.capture.stop.prevent="inputTree.prevInput(props.inputId)"
                                @keydown.tab.prevent="inputTree.nextInput(props.inputId)" />
                        </div>
                    </div>

                </div>
            </div>
            <div class="dropdown-menu m-0 p-0 overflow-visible" ref="tagInputContainer" data-bs-display="static">

                <ul class="list-unstyled mb-0" v-if="edit">
                    <li v-if="imageTags" class="bg-light m-0 p-0 pb-1 pt-1 ps-1 rounded-top" style="width: 300px;">
                        <TagBadge @delete="removeTag(tag)" :show-delete="true" :tag="tag.value" :color="tag.color"
                            v-for="tag in imageTags" class="me-1"/>
                    </li>
                    <p class="m-0 ms-2 me-2 text-muted text-nowrap" style="font-size: 14px;">Select a tag or create one
                    </p>
                    <li @mouseover="selectedIndex = index" @click.prevent.stop="selectOption" :class="optionClass(index)"
                        v-for="tag, index in filteredTagList" style="cursor: pointer;"><a class="ms-2" href="#">
                            <TagBadge :tag="tag.value" :color="tag.color" />
                        </a></li>
                    <li @mouseover="selectedIndex = filteredTagList.length" @click.prevent.stop="selectOption"
                        v-if="isCreatePossible" :class="optionClass(filteredTagList.length) + ' rounded-bottom'"
                        style="cursor: pointer;">
                        <span class="text-muted ms-1">Create </span>
                        <TagBadge :tag="tagInput" color="grey" />
                    </li>
                </ul>
            </div>
        </div>
    </div>
</template>

<style scoped>
/* .test-wraped { */
/* display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2; */
/* number of lines to show */
/* line-clamp: 2;
    overflow: hidden;
    cursor: pointer; */
/* } */


.input-container {
    position: relative;
    /* top: 0; */

}

.drop-menu {
    position: absolute;
    z-index: 9000 !important;
}
</style>