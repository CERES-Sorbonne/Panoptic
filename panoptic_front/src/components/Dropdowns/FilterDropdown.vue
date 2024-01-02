<script setup lang="ts">

/**
 * FilterDropdown view
 * Interface to FilterManager functions
 * Allows to create a new Filter from start or modify an existing filter.
 */

import { computed, onMounted, ref, watch } from 'vue';
import PropertySelection from '../inputs/PropertySelection.vue';
import { PropertyID, PropertyType} from '@/data/models';
import { useProjectStore } from '@/data/projectStore'
import OperatorDropdown from '../inputs/OperatorDropdown.vue';
import ColorPropInputNoDropdown from '../inputs/ColorPropInputNoDropdown.vue';
import TagInput from '../tags/TagInput.vue';
import StandaloneTextInput from '../inputs/multiline/StandaloneTextInput.vue';
import Dropdown from './Dropdown.vue';
import { Filter, FilterManager, FilterOperator, operatorHasInput } from '@/core/FilterManager';
import { propertyDefault } from '@/data/builder';
import { isTag } from '@/utils/utils';
const store = useProjectStore()
enum State {
    CLOSED = 0,
    TYPE = 1, // chose filter propertyId
    MODE = 2 // chose operator and value
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
    const prop = store.data.properties[filter.value.propertyId]
    return prop
})


// Dropdown functions

function show() {
    mode.value = props.mode
    if (props.mode == State.MODE && props.filterId == undefined) {
        updateProperty(props.propertyId)
    }
}

function hide() {
    if (dropdownElem.value) dropdownElem.value.hide()
}

function onHide() {
    mode.value = State.CLOSED
}

// FilterManager functions

function deleteFilter() {
    hide()
    props.manager.deleteFilter(filterId.value)
    props.manager.update(true)
}

function updateProperty(propId) {
    let filter = props.manager.addNewFilter(propId, props.parentId)
    props.manager.update(true)
    localFilterId.value = filter.id
    mode.value = State.MODE
}

function updateOperator(operator: FilterOperator) {
    props.manager.updateFilter(filterId.value, { operator })
    props.manager.update(true)
    if (inputElem.value) {
        inputElem.value.focus()
    }
}

function updateValue() {
    // console.log('update value')
    props.manager.updateFilter(filterId.value, { value: localValue.value })
    props.manager.update(true)
}

function updateIfChanged() {
    if (!filter.value) return

    const prop = store.data.properties[filter.value.propertyId]
    if (isTag(prop.type)) return

    const value = localValue.value ?? propertyDefault(prop.type)
    if (filter.value.value != value) {
        updateValue()
    }
}

// LocalValue reactivity

function updateLocal() {
    if (!filter.value) return
    localValue.value = filter.value.value
}
onMounted(updateLocal)
watch(() => filter.value?.value, () => updateLocal())

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
                    <PropertySelection v-if="mode == State.TYPE" @select="updateProperty"
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
                                :property="store.data.properties[filter.propertyId]" ref="inputElem" @hide="hide"
                                @update:model-value="updateValue" />
                            <ColorPropInputNoDropdown v-else-if="filterProperty.type == PropertyType.color"
                                :property="filterProperty" v-model="localValue"
                                @update:model-value="() => { hide(); updateIfChanged() }" />
                            <StandaloneTextInput v-else :no-html="true" v-model="localValue" :width="-1" :min-height="20"
                                :no-nl="store.data.properties[filter.propertyId].type == PropertyType.number"
                                :url-mode="store.data.properties[filter.propertyId].type == PropertyType.url"
                                :only-number="store.data.properties[filter.propertyId].type == PropertyType.number"
                                @blur="updateIfChanged" :auto-focus="true" ref="inputElem" />
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