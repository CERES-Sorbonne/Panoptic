<script setup lang="ts">
import { useDataStore } from '@/data/dataStore';
import { ModalId, PropertyGroup, PropertyGroupId, PropertyGroupNode } from '@/data/models';
import { computed, onMounted, ref, watch } from 'vue';
import PropertyOptions from './PropertyOptions.vue';
import TextInput from '../property_inputs/TextInput.vue';
import { TabManager } from '@/core/TabManager';
import draggableComponent from 'vuedraggable';
import { usePanopticStore } from '@/data/panopticStore';
import Dropdown from '../dropdowns/Dropdown.vue';
import WithToolTip from '../tooltips/withToolTip.vue';

const data = useDataStore()
const panoptic = usePanopticStore()

const props = defineProps<{
    tab: TabManager
    node: PropertyGroupNode,
    menuOpen?: boolean
}>()

const open = ref(true)
const editName = ref(false)
const localName = ref('')

const properties = computed(() => props.node.propertyIds.map(i => data.properties[i]))

const group = computed(() => {
    if (props.node.groupId >= 0) {
        return data.propertyGroups[props.node.groupId]
    }
    if (props.node.groupId == PropertyGroupId.DEFAULT) {
        return { id: PropertyGroupId.DEFAULT, name: 'default' }
    }
    if (props.node.groupId == PropertyGroupId.COMPUTED) {
        return { id: PropertyGroupId.COMPUTED, name: 'computed' }
    }
})

const isEditable = computed(() => group.value.id >= 0)

function toggle() {
    open.value = !open.value
}

function updateName(name) {
    data.updatePropertyGroup(group.value.id, localName.value)
}

function updateLocalName() {
    localName.value = group.value.name
}

function deleteGroup() {
    data.deletePropertyGroup(group.value.id)
}

async function deleteProperties() {
    let properties = data.propertyList.filter(p => p.propertyGroupId == props.node.groupId)
    for (let prop of properties) {
        await data.deleteProperty(prop.id)
    }
    if (props.node.groupId >= 0) {
        await data.deletePropertyGroup(props.node.groupId)
    }

}

async function log(e) {
    if (e.added) {
        let id = e.added.element
        const prop = data.properties[id]
        let groupId = props.node.groupId
        if (groupId < 0) {
            groupId = null
        }
        await data.updateProperty(prop.id, prop.name, groupId)
        await data.triggerPropertyTreeChange()
    }
    if (e.moved) {
        await data.triggerPropertyTreeChange()
    }
}

onMounted(updateLocalName)
watch(props, updateLocalName)

</script>

<template>
    <div class="prop-container" v-if="data.propertyGroups[props.node.groupId] || props.node.groupId < 0">
        <draggableComponent :list="props.node.propertyIds" :item-key="a => a"
            :group="props.node.groupId > 0 || props.node.groupId == PropertyGroupId.DEFAULT ? 'properties' : undefined"
            @change="log">
            <template #header>
                <div class="d-flex group-container" @click="toggle">
                    <div v-if="open"><i class="bi bi-caret-down-fill" /></div>
                    <div v-if="!open"><i class="bi bi-caret-right-fill" /></div>
                    <template v-if="props.menuOpen">
                        <div v-if="!editName" class="ms-2 text-capitalize overflow-hidden">{{ group.name }}</div>
                        <div v-if="editName" class="ms-2">
                            <TextInput :auto-focus="true" v-model="localName" style="background-color: white;"
                                :min-height="25" :width="135" @submit="updateName" @cancel="updateLocalName"
                                @blur="editName = false" />
                        </div>
                        <div class="flex-grow-1"></div>
                        <Dropdown @click.prevent.stop="" v-if="props.node.groupId >= PropertyGroupId.DEFAULT">
                            <template #button><i class="bb bi bi-three-dots" /></template>
                            <template #popup="{ hide }">
                                <div class="p-1">
                                    <template v-if="isEditable">
                                        <div class="bb" @click="editName = true; hide();">
                                            {{ $t('main.menu.editName') }}
                                        </div>
                                        <div class="bb" @click="deleteGroup">
                                            {{ $t('main.menu.removeGroup') }}
                                        </div>
                                    </template>
                                    <div class="bb" @click="deleteProperties(); hide();">
                                        {{ $t('main.menu.deleteGroupAndProperties') }}
                                    </div>
                                </div>
                            </template>
                        </Dropdown>
                        <div v-if="props.node.groupId >= -1" class="bb me-2"
                            @click.stop.prevent="panoptic.showModal(ModalId.PROPERTY, { group: props.node.groupId })">
                            <WithToolTip :message="$t('main.menu.addNewPropertyToGroup')">
                                <i class="bi bi-plus" />
                            </WithToolTip>
                        </div>
                    </template>
                </div>
            </template>
            <template #item="{ element, index }">
                <div v-if="open && properties.length && data.properties[element]" class="ps-1 pe-1">
                    <div class="property-item">
                        <PropertyOptions :tab="props.tab" :property="data.properties[element]" :open="props.menuOpen" />
                    </div>
                </div>
            </template>
        </draggableComponent>
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