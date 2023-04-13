<script setup lang="ts">
import { Image, Property, PropertyValue } from '@/data/models';
import { computed, nextTick, ref } from 'vue';
import { PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';
import { PropertyRef } from '@/data/models'
import PropertyIcon from '../properties/PropertyIcon.vue';

const props = defineProps({
    property: Object as () => PropertyRef,
    maxSize: String
})

const edit = ref(false)
const inputElem = ref(null)


const isSet = computed(() => props.property.value || props.property.value == 0)
const type = computed(() => props.property.type)


// function setEdit(value: Boolean) {
//     if (value) {
//         edit.value = true
//         nextTick(() => {
//             if (!input.value) {
//                 return
//             }
//             input.value.focus()
//         })
//     }
//     else {
//         globalStore.addOrUpdatePropertyToImage(props.property.imageSHA1, props.property.propertyId, props.property.value)
//         edit.value = false
//         if (props.property.value == '') {
//             props.property.value = undefined
//         }
//     }
// }

function setEdit(value: Boolean) {
    if (value) {
        edit.value = true
        document.addEventListener('click', handleContainerClick, true)
        nextTick(() => {
            if (!inputElem.value) {
                return
            }
            inputElem.value.focus()
        })
    }
    else {
        document.removeEventListener('click', handleContainerClick)
        globalStore.addOrUpdatePropertyToImage(props.property.imageSHA1, props.property.propertyId, props.property.value)
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
        
        if(!elemIsInput(event.target, 10)) {
            event.stopPropagation()
        }
    }
};

function elemIsInput(elem: HTMLElement, depth: number = 0): Boolean {
    if(elem.getAttribute('is-input')) {
        return true
    }
    if(depth > 0 && elem.parentElement) {
        return elemIsInput(elem.parentElement, depth-1)
    }
    return false
}

</script>


<template>
    <form @submit.prevent="setEdit(false)" is-input="true">
        <div class="input-group bg-light overflow-hidden" :style="'width:'+props.maxSize+'px;'" @click="setEdit(true)">
            <span class="input-group-text small bg-light text-dark me-1">
                <span class="me-1">
                    <input v-if="type == PropertyType.checkbox" class="form-check-input" type="checkbox" v-model="props.property.value" @change="setEdit(false)">
                    <span @click="setEdit(true)" v-else><PropertyIcon :type="property.type"/> </span>
                </span>
                <span v-if="!edit && !(type == PropertyType.checkbox)" @click="setEdit(true)">
                    <span v-if="!isSet" class="text-secondary">None</span>
                    <span v-else-if="type != PropertyType.color">{{ props.property.value }}</span>
                </span>
                <span v-if="type == PropertyType.checkbox">{{ globalStore.properties[props.property.propertyId].name
                }}</span>
            </span>
            <template v-if="type == PropertyType.color && isSet">
                <input type="color" class="form-control small" v-model="props.property.value" />
            </template>
            <template v-if="edit">
                <template
                    v-if="type == PropertyType.string || type == PropertyType.path || type == PropertyType.image_link || type == PropertyType.url">
                    <input type="text" class="form-control small" ref="inputElem" v-model="props.property.value"/>
                </template>

                <input v-if="type == PropertyType.number" type="number" class="form-control small" ref="inputElem"
                    v-model="props.property.value"/>
                <input v-if="type == PropertyType.date" type="date" class="form-control small" ref="inputElem"
                    v-model="props.property.value"/>
                <input v-if="type == PropertyType.color" type="color" class="form-control small" ref="inputElem"
                    v-model="props.property.value"/>
            </template>
        </div>
    </form>
</template>


<style>
.small {
    margin: 0px !important;
    padding: 0px !important;
    border: 0 !important;
    border-radius: 0 !important;
}
</style>