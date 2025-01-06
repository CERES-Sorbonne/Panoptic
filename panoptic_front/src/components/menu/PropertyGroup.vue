<script setup lang="ts">
import { useDataStore } from '@/data/dataStore';
import { PropertyGroup } from '@/data/models';
import { computed, onMounted, ref, watch } from 'vue';
import PropertyOptions from './PropertyOptions.vue';
import TextInput from '../property_inputs/TextInput.vue';

const data = useDataStore()


const props = defineProps<{
    group: PropertyGroup,
    menuOpen?: boolean
}>()

const open = ref(true)
const editName = ref(false)
const localName = ref('')

const properties = computed(() => data.propertyList.filter(p => p.propertyGroupId == props.group.id))

function toggle() {
    open.value = !open.value
}

function updateName(name) {
    data.updatePropertyGroup(props.group.id, localName.value)
}

function updateLocalName() {
    localName.value = props.group.name
}

function deleteGroup() {
    data.deletePropertyGroup(props.group.id)
}

onMounted(updateLocalName)
watch(props, updateLocalName)

</script>

<template>
    <div class="prop-container">
        <div class="d-flex group-container" @click="toggle">
            <div v-if="open"><i class="bi bi-caret-down-fill" /></div>
            <div v-if="!open"><i class="bi bi-caret-right-fill" /></div>
            <template v-if="props.menuOpen">
                <div v-if="!editName" class="ms-2 text-capitalize overflow-hidden">{{ props.group.name }}</div>
                <div v-if="editName" class="ms-2">
                    <TextInput :auto-focus="true" v-model="localName" style="background-color: white;" :min-height="25" :width="135" @submit="updateName" @cancel="updateLocalName" @blur="editName=false"/>
                </div>
                <div class="flex-grow-1"></div>
                <div v-if="!editName" class="bb me-1" @click.stop="editName = true"><i class="bi bi-pencil" /></div>
                <div class="bb me-1" @click.stop="deleteGroup"><i class="bi bi-x" /></div>
            </template>
            
        </div>
        <div v-if="open && properties.length" class="ps-1 pe-1 pt-1">
            <template v-for="property in properties">
                <div class="property-item" >
                    <PropertyOptions :property="property" :open="props.menuOpen" />
                </div>

            </template>
        </div>
    </div>
</template>

<style scoped>

.group-container {
    cursor: pointer;
    background-color: rgba(195, 207, 217, 0.158);
    padding: 4px 0px 2px 4px;
}

.group-container:hover {
    background-color: rgba(195, 207, 217, 0.397);
}

.prop-container {
    border: 1px solid var(--border-color);
}
</style>