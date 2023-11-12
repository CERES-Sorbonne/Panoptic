<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';
import { PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';
import { PropertyRef } from '@/data/models'
import PropertyIcon from '../properties/PropertyIcon.vue';
import * as inputTree from '@/utils/inputTree'
import TagBadge from '../tagtree/TagBadge.vue'
import ColorPropInput from './ColorPropInput.vue';

const props = defineProps({
    property: Object as () => PropertyRef,
    maxSize: String,
    inputId: Array<number>
})

const edit = ref(false)
const inputElem = ref(null)
const clickableElem = ref(null)


const isSet = computed(() => props.property.value || props.property.value == 0)
const type = computed(() => props.property.type)

function setEdit(value: Boolean) {
    if (props.property.propertyId < 0) {
        edit.value = false
        return
    }
    if (value) {
        edit.value = true
        nextTick(() => {
            document.addEventListener('click', handleContainerClick, true)
            if (!inputElem.value) {
                return
            }
            inputElem.value.focus()
        })
    }
    else {
        document.removeEventListener('click', handleContainerClick)
        console.log('start here')
        const img = globalStore.images[props.property.imageId]
        globalStore.setPropertyValue(props.property.propertyId, img, props.property.value)
        edit.value = false
        if (props.property.value == '') {
            props.property.value = undefined
        }
    }
}

const handleContainerClick = (event: any) => {
    if (!edit.value) {
        return
    }
    if (inputElem.value && !inputElem.value.contains(event.target)) {
        setEdit(false)

        if (!elemIsInput(event.target, 10)) {
            event.stopPropagation()
        }
    }
};

function elemIsInput(elem: HTMLElement, depth: number = 0): Boolean {
    if (elem.getAttribute('is-input')) {
        return true
    }
    if (depth > 0 && elem.parentElement) {
        return elemIsInput(elem.parentElement, depth - 1)
    }
    return false
}


function inputType(type: PropertyType) {
    switch (type) {
        case PropertyType.number:
            return 'number'
        case PropertyType.date:
            return 'date'
        case PropertyType.color:
            return 'color'
        case PropertyType.checkbox:
            return null
        case PropertyType.url:
            return 'url'
        case PropertyType._folders:
            return null
        default:
            return 'text'
    }
}


onMounted(() => {
    if (props.inputId != undefined) {
        inputTree.registerInput(props.inputId, clickableElem.value)
    }
})

</script>


<template>
    <form @submit.prevent="setEdit(false)" is-input="true" class="overflow-hidden p-0 m-0">
        <div class="d-flex flex-row container2" @click="setEdit(true)" ref="clickableElem">
            <div class="me-1 text-nowrap">
                <span class="me-1">
                    <!-- Affichage d'un icone pour désigner la propriété sauf dans le cas d'une checkbox où l'input checkbox prend la place de l'icone -->
                    <input v-if="type == PropertyType.checkbox" class="small-input" type="checkbox"
                        v-model="props.property.value" @change="setEdit(false)" ref="inputElem"
                        @keydown.shift.tab.capture.stop.prevent="inputTree.prevInput(props.inputId)"
                        @keydown.tab.prevent="inputTree.nextInput(props.inputId)">
                    <span v-else>
                        <!-- pour un input de type url l'icone sert à accéder au lien -->
                        <a v-if="type == PropertyType.url" :href="props.property.value" target="_blank">
                            <PropertyIcon :type="property.type" />
                        </a>
                        <PropertyIcon :type="property.type" v-else />
                    </span>
                </span>
                <!-- On affiche la valeur de la propriété -->
                <span v-if="!edit && !(type == PropertyType.checkbox)" @click="setEdit(true)">
                    <span v-if="!isSet" class="text-secondary">None</span>
                    <span v-else-if="type == PropertyType._folders">
                        <TagBadge :tag="globalStore.folders[props.property.value].name" :color="-1" />
                    </span>
                    <span v-else-if="type != PropertyType.color">{{ props.property.value }}</span>
                </span>
            </div>
            <!-- on affiche l'input pour le type de la propriété sauf si le type n'est pas standard (inputType(type) renvoie null dans ces cas là) -->
            <div v-if="edit && inputType(type)" class="">
                
                <input :type="inputType(type)" class="small-input2" ref="inputElem" v-model="props.property.value"
                    @keydown.shift.tab.capture.stop.prevent="inputTree.prevInput(props.inputId)"
                    @keydown.tab.prevent="inputTree.nextInput(props.inputId)" />
            </div>
            <div v-if="type == PropertyType.checkbox">
                {{ globalStore.properties[props.property.propertyId].name }}
            </div>
        </div>
    </form>
</template>


<style scoped>
.small-input2 {
    /* margin: 0px !important;
    padding: 0px !important;
    border: 0 !important;
    border-radius: 0 !important;
    border: none;
    background-image: none;
    background-color: transparent;
    -webkit-box-shadow: none;
    -moz-box-shadow: none;
    box-shadow: none;
    text-align: left; */
    font-size: 14px;
    font-family: Inter, Din, Barlow, 'IBM Plex Sans', sans-serif !important;
    color: var(--text-color);
    position: relative;
    top:-1px;
    left: 0px;

}

.container2 {
    height: 26px;
}

</style>