<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import PropertyModeDropdown from './PropertyModeDropdown.vue';
import PropertyTypeDropdown from './PropertyTypeDropdown.vue';
import PropertySelection from '../inputs/PropertySelection.vue';
import { FilterManager } from '@/utils/filter';
import { Filter, PropertyType, operatorHasInput } from '@/data/models';
import { globalStore } from '@/data/store';
import OperatorDropdown from '../inputs/OperatorDropdown.vue';
import TagDropdown from '../inputs/TagDropdown.vue';
import PropertyInput2 from '../inputs/PropertyInput2.vue';
import TagInputNoDropdown from '../inputs/TagInputNoDropdown.vue';

enum State {
    CLOSED = 0,
    TYPE = 1,
    MODE = 2
}

const props = defineProps({
    manager: FilterManager,
    mode: { type: Number, default: 1 }
})


const buttonElem = ref(null)
const inputElem = ref(null)



const mode = ref(State.CLOSED)
const filterId = ref(-1)
const filter = computed(() => {
    if (filterId.value == -1) return
    return props.manager.filterIndex[filterId.value] as Filter
})

const filterProperty = computed(() => {
    if (filter.value == undefined) return
    const prop = globalStore.properties[filter.value.propertyId]
    return prop
})

function show() {
    mode.value = props.mode
}
function hide() {
    mode.value = State.CLOSED
}

function selectProperty(propId) {
    let filter = props.manager.addNewFilter(propId)
    filterId.value = filter.id
    mode.value = State.MODE
}

onMounted(() => {
    buttonElem.value.addEventListener('show.bs.dropdown', show)
    buttonElem.value.addEventListener('hide.bs.dropdown', hide)
})

watch(() => filter.value?.operator, () => {
    if(inputElem.value) {
        inputElem.value.focus()
    }
})

</script>

<template>
    <div class="" style="position: static; cu">
        <div data-bs-toggle="dropdown" aria-expanded="false" data-bs-auto-close="outside" ref="buttonElem">
            <slot></slot>
        </div>
        <div class="dropdown-menu container-size" aria-labelledby="dropdownMenuOffset">
            <template v-if="mode != State.CLOSED">
                <PropertySelection v-if="mode == State.TYPE" @select="selectProperty" />
                <div v-if="mode == State.MODE">
                    <div class="d-flex mode-header">
                        <div class="me-3">{{ filterProperty.name }}</div>
                        <OperatorDropdown :property-id="filter.propertyId"
                            v-model="(props.manager.filterIndex[filterId] as Filter).operator" />
                        <div class="flex-fill"></div>
                        <!-- <div><i class="bi bi-three-dots"></i></div> -->
                        <div><i class="bi bi-trash-fill"></i></div>
                    </div>
                    <div class="me-2" v-if="operatorHasInput(filter.operator)" style="width: 100%;">
                        <TagInputNoDropdown v-if="filterProperty.type == PropertyType.multi_tags || filterProperty.type == PropertyType.tag"
                            v-model="filter.value" :property-id="filter.propertyId" ref="inputElem"/>
                        <PropertyInput2 v-else :type="filterProperty.type" v-model="filter.value" />
                    </div>
                </div>
            </template>
        </div>
    </div>
</template>

<style scoped>
.mode-header {
    font-size: 13px;
    margin-bottom: 4px;
}

.container-size {
    width: 250px;

    padding: 4px 8px;
}
</style>