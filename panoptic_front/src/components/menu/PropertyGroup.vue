<script setup lang="ts">
import { useDataStore } from '@/data/dataStore';
import { DbCommit, ModalId, PropertyGroup, PropertyGroupId, PropertyGroupNode } from '@/data/models';
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import PropertyOptions from './PropertyOptions.vue';
import TextInput from '../property_inputs/TextInput.vue';
import { TabManager } from '@/core/TabManager';
import draggableComponent from 'vuedraggable';
import { usePanopticStore } from '@/data/panopticStore';
import Dropdown from '../dropdowns/Dropdown.vue';
import WithToolTip from '../tooltips/withToolTip.vue';

const data = useDataStore()
const panoptic = usePanopticStore()
const { t } = useI18n()

const props = defineProps<{
    tab: TabManager
    node: PropertyGroupNode,
    menuOpen?: boolean
}>()

const open = ref(true)
const editName = ref(false)
const localName = ref('')

const properties = computed(() => props.node.propertyIds.map(i => data.properties[i]))

const allVisible = computed(() => props.node.propertyIds.map(id => props.tab.isVisibleProperty(id)).filter(v => !v).length == 0)

const group = computed(() => {
    if (props.node.groupId >= 0) {
        return data.propertyGroups[props.node.groupId]
    }
    if (props.node.groupId == PropertyGroupId.DEFAULT) {
        return { id: PropertyGroupId.DEFAULT, name: 'default' }
    }
    if (props.node.groupId == PropertyGroupId.METADATA) {
        return { id: PropertyGroupId.METADATA, name: t('common.properties.metadata') }
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
    const commit: DbCommit = { emptyProperties: properties.map(p => p.id)}
    await data.sendCommit(commit)

    const commit2: DbCommit = { emptyPropertyGroups: [props.node.groupId] }
    await data.sendCommit(commit2)
    // if (props.node.groupId >= 0) {
    //     await data.deletePropertyGroup(props.node.groupId)
    // }

}

async function log(e) {
    if (e.added) {
        let id = e.added.element
        const prop = data.properties[id]
        let groupId = props.node.groupId
        if (groupId < 0) {
            groupId = null
        }
        prop.propertyGroupId = groupId
        await data.updateProperty(prop.id, prop.name, groupId)
        await data.triggerPropertyTreeChange()
    }
    if (e.moved) {
        await data.triggerPropertyTreeChange()
    }
}

function toggleVisible() {
    if (allVisible.value) {
        props.tab.setVisibleProperties(props.node.propertyIds, false)
    } else {
        props.tab.setVisibleProperties(props.node.propertyIds, true)
    }
}

onMounted(updateLocalName)
watch(props, updateLocalName)

</script>

<template>
    <div class="prop-group" v-if="data.propertyGroups[props.node.groupId] || props.node.groupId < 0">
        <draggableComponent :list="props.node.propertyIds" :item-key="a => a"
            :group="props.node.groupId > 0 || props.node.groupId == PropertyGroupId.DEFAULT ? 'properties' : undefined"
            @change="log">
            <template #header>
                <div class="group-header" @click="toggle">
                    <span class="group-caret">
                        <i :class="open ? 'bi bi-chevron-down' : 'bi bi-chevron-right'" />
                    </span>

                    <template v-if="props.menuOpen">
                        <span v-if="!editName" class="group-name">{{ group.name }}</span>
                        <span v-else class="group-edit" @click.stop>
                            <TextInput :auto-focus="true" v-model="localName" style="background-color: white;"
                                :min-height="22" :width="135" @submit="updateName" @cancel="updateLocalName"
                                @blur="editName = false" />
                        </span>

                        <div class="group-actions">
                            <Dropdown @click.prevent.stop="" v-if="props.node.groupId >= PropertyGroupId.DEFAULT">
                                <template #button><i class="group-action bi bi-three-dots" /></template>
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
                            <span v-if="props.node.groupId >= -1" class="group-action"
                                @click.stop.prevent="panoptic.showModal(ModalId.PROPERTY, { group: props.node.groupId })">
                                <WithToolTip :message="$t('main.menu.addNewPropertyToGroup')">
                                    <i class="bi bi-plus-lg" />
                                </WithToolTip>
                            </span>
                        </div>
                    </template>

                    <span v-if="props.node.propertyIds.length" class="group-eye" @click.stop="toggleVisible">
                        <i :class="'bi bi-eye text-' + (allVisible ? 'primary' : 'secondary')"></i>
                    </span>
                </div>
            </template>
            <template #item="{ element, index }">
                <div v-if="open && properties.length && data.properties[element]" class="property-item">
                    <PropertyOptions :tab="props.tab" :property="data.properties[element]" :open="props.menuOpen" />
                </div>
            </template>
        </draggableComponent>
    </div>
</template>


<style scoped>
.prop-group {
    margin-bottom: 2px;
}

.group-header {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 24px;
    padding: 0 var(--spacing-sm);
    cursor: pointer;
    white-space: nowrap;
}

.group-header:hover {
    background-color: var(--hover-bg);
}

.group-caret {
    width: 16px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    color: var(--text-tertiary);
    flex-shrink: 0;
}

.group-name {
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.02em;
    overflow: hidden;
    text-overflow: ellipsis;
}

.group-edit {
    display: inline-flex;
    align-items: center;
}

.group-actions {
    display: flex;
    align-items: center;
    gap: 2px;
    margin-left: auto;
    opacity: 0;
}

.group-header:hover .group-actions {
    opacity: 1;
}

.group-action {
    width: 18px;
    height: 18px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    font-size: 12px;
    color: var(--text-tertiary);
    cursor: pointer;
}

.group-action:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.group-eye {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin-left: auto;
    padding-right: 2px;
    font-size: 12px;
    flex-shrink: 0;
    cursor: pointer;
}

/* When actions are present they own the margin-left:auto, so the eye sits next to them */
.group-actions + .group-eye {
    margin-left: 4px;
}

.property-item {
    padding: 0;
    border: none;
}
</style>