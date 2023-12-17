<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import PropertySelection from '../inputs/PropertySelection.vue';
import { Filter, PropertyID, PropertyType, isTag, operatorHasInput, propertyDefault } from '@/data/models';
import { globalStore } from '@/data/store';
import OperatorDropdown from '../inputs/OperatorDropdown.vue';
import PropertyInput2 from '../inputs/PropertyInput2.vue';
import * as bootstrap from 'bootstrap'
import ColorPropInputNoDropdown from '../inputs/ColorPropInputNoDropdown.vue';
import TextInput from '../inputs/TextInput.vue';
import TagInput from '../tags/TagInput.vue';
import StandaloneTextInput from '../inputs/multiline/StandaloneTextInput.vue';
import Dropdown from './Dropdown.vue';
import { FilterManager, FilterOperator } from '@/core/FilterManager';

enum State {
    CLOSED = 0,
    TYPE = 1,
    MODE = 2
}

const props = defineProps({
    manager: FilterManager,
    mode: { type: Number, default: 1 },
    propertyId: Number,
    parentId: Number,
    filterId: Number,
    parent: HTMLElement
})


const dropdownElem = ref(null)
const inputElem = ref(null)
const popupElem = ref(null)


const mode = ref(State.CLOSED)

const localFilterId = ref(-1)
const localValue = ref(null)

const filterId = computed(() => props.filterId != undefined ? props.filterId : localFilterId.value)
const filter = computed(() => {
    if (filterId.value == undefined || filterId.value == -1) return
    return (props.manager.filterIndex[filterId.value] as Filter)
})

const filterProperty = computed(() => {
    if (filter.value == undefined) return
    const prop = globalStore.properties[filter.value.propertyId]
    return prop
})

function show() {
    mode.value = props.mode
    if (props.mode == State.MODE && props.filterId == undefined) {
        selectProperty(props.propertyId)
    }
}
function onHide() {
    mode.value = State.CLOSED
}

function onBlur() {
    if (!filter.value) return

    const prop = globalStore.properties[filter.value.propertyId]
    if (isTag(prop.type)) return
    // console.log(prop.type)
    const value = localValue.value ?? propertyDefault(prop.type)

    if (filter.value.value != value) {
        // console.log('blur', filter.value.value, ':', value)
        updateValue()
    }
}

function selectProperty(propId) {
    let filter = props.manager.addNewFilter(propId, props.parentId)
    props.manager.update(true)
    localFilterId.value = filter.id
    mode.value = State.MODE
}

function deleteFilter() {
    hide()
    props.manager.deleteFilter(filterId.value)
    props.manager.update(true)
}

function hide() {
    if (dropdownElem.value) dropdownElem.value.hide()
}

function updateOperator(operator: FilterOperator) {
    props.manager.updateFilter(filterId.value, { operator })
    props.manager.update(true)
}

function updateValue() {
    // console.log('update value')
    props.manager.updateFilter(filterId.value, { value: localValue.value })
    props.manager.update(true)
}

function updateLocal() {
    if (!filter.value) return
    const property = globalStore.properties[filter.value.propertyId]
    localValue.value = filter.value.value ?? propertyDefault(property.type)
}

onMounted(updateLocal)
watch(() => filter.value?.value, () => {
    updateLocal()
})

watch(() => filter.value?.operator, () => {
    if (inputElem.value) {
        inputElem.value.focus()
    }
})

</script>

<template>
    <Dropdown ref="dropdownElem" @show="show" @hide="onHide" :parent="props.parent">
        <template #button>
            <div class="m-0 p-0">
                <slot></slot>
            </div>

        </template>

        <template #popup>
            <div class="container-size bg-white" ref="popupElem">
                <template v-if="mode != State.CLOSED">
                    <PropertySelection v-if="mode == State.TYPE" @select="selectProperty"
                        :ignore-ids="[PropertyID.folders]" />
                    <div v-if="mode == State.MODE">
                        <div class="d-flex mode-header">
                            <div class="me-3">{{ filterProperty.name }}</div>
                            <OperatorDropdown :property-id="filter.propertyId" :model-value="filter.operator"
                                @update:model-value="updateOperator" :parent="popupElem" />
                            <div class="flex-fill"></div>
                            <!-- <div><i class="bi bi-three-dots"></i></div> -->
                            <div><i class="bi bi-trash-fill" @click="deleteFilter"></i></div>
                        </div>
                        <div class="me-2" v-if="operatorHasInput(filter.operator)" style="width: 100%;">
                            <TagInput
                                v-if="filterProperty.type == PropertyType.multi_tags || filterProperty.type == PropertyType.tag"
                                v-model="localValue" :auto-focus="true"
                                :property="globalStore.properties[filter.propertyId]" ref="inputElem" @hide="hide" @update:model-value="updateValue" />
                            <ColorPropInputNoDropdown v-else-if="filterProperty.type == PropertyType.color"
                                :property="filterProperty" v-model="localValue" @update:model-value="() => {hide(); onBlur()}" />
                            <StandaloneTextInput
                                v-else
                                :no-html="true" v-model="localValue" :width="-1" :min-height="20"
                                :no-nl="globalStore.properties[filter.propertyId].type == PropertyType.number"
                                :url-mode="globalStore.properties[filter.propertyId].type == PropertyType.url"
                                :only-number="globalStore.properties[filter.propertyId].type == PropertyType.number"
                                @blur="onBlur" :auto-focus="true" ref="inputElem" />
                            <!-- <PropertyInput2 v-else :type="filterProperty.type" v-model="localValue" /> -->
                        </div>
                    </div>
                </template>
            </div>

        </template>


    </Dropdown>
</template>

<style scoped>
.mode-header {
    font-size: 13px;
    margin-bottom: 4px;
}

.container-size {
    width: 250px;
    border-radius: 5px;
    padding: 4px 8px;
}
</style>