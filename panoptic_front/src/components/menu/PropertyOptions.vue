<script setup lang="ts">
import { ModalId, Property, PropertyID, PropertyMode, PropertyType } from '@/data/models';
import { computed, nextTick, ref, watch } from 'vue';
import PropertyIcon from '../properties/PropertyIcon.vue';
import wTT from '../tooltips/withToolTip.vue';
import TagMenu from '../tags/TagMenu.vue';
import { useProjectStore } from '@/data/projectStore';
import { Filter } from '@/core/FilterManager';
import { useDataStore } from '@/data/dataStore';
import { isTag, objValues } from '@/utils/utils';
import { usePanopticStore } from '@/data/panopticStore';
import { Dropdowns } from '@/data/dropdowns';
import { useI18n } from 'vue-i18n';
import Dropdown from '../dropdowns/Dropdown.vue';
import { TabManager } from '@/core/TabManager';

const { t } = useI18n(({ useScope: 'global' }))

const panoptic = usePanopticStore()
const project = useProjectStore()
const data = useDataStore()

const props = defineProps<{
    tab: TabManager
    property: Property,
    open?: boolean
}>()

const valuesOpen = ref(false)
const editName = ref(false)
const localName = ref('')
const nameInput = ref<HTMLInputElement>()

const propertyVisible = computed(() => props.tab.state.visibleProperties[props.property.id] == true)

const isInFilter = computed(() => props.tab.collection.filterManager.state.filter.filters.some((f) => !f.isGroup && (f as Filter).propertyId == props.property.id))
const isInGroups = computed(() => props.tab.collection.groupManager.state.groupBy.includes(props.property.id))
const isInSort = computed(() => props.tab.collection.sortManager.state.sortBy.includes(props.property.id))
const filterId = computed(() => {
    if (!isInFilter.value) return undefined
    return props.tab.collection.filterManager.state.filter.filters.find((f) => !f.isGroup && (f as Filter).propertyId == props.property.id).id
})
const filterManager = () => props.tab.collection.filterManager
const sha1Mode = computed(() => props.tab.getSha1Mode())

function toggleVisible() {
    if (editName.value) return
    if (propertyVisible.value) {
        props.tab.setVisibleProperty(props.property.id, false)
    } else {
        props.tab.setVisibleProperty(props.property.id, true)
    }
}

function startRename() {
    localName.value = props.property.name
    editName.value = true
    nextTick(() => nameInput.value?.focus())
}

function cancelRename() {
    editName.value = false
}

function toggleValuesMenu() {
    if (props.property.type != PropertyType.tag && props.property.type != PropertyType.multi_tags) {
        return
    }
    valuesOpen.value = !valuesOpen.value
}

function setSort() {
    if (!isInSort.value) {
        props.tab.collection.sortManager.setSort(props.property.id)
    } else {
        props.tab.collection.sortManager.delSort(props.property.id)
    }
}

function setGroup() {
    if (!isInGroups.value) {
        props.tab.collection.groupManager.setGroupOption(props.property.id)
    } else {
        props.tab.collection.groupManager.delGroupOption(props.property.id)
    }
}

function deleteProperty() {
    if (confirm(t('common.properties.delete') + ': ' + props.property.name + ' ?   ' + props.property.id))
        data.deleteProperty(props.property.id)
}

async function renameProperty() {
    if (localName.value == '' || localName.value == props.property.name) {
        editName.value = false
        return
    }
    await data.updateProperty(props.property.id, localName.value)
    editName.value = false
}

function setFilter() {
    const manager = filterManager()
    if (!isInFilter.value) {
        manager.addNewFilter(props.property.id)
        Dropdowns.filter.show()
    } else {
        manager.deleteFilter(filterId.value)
        Dropdowns.filter.hide()
    }

}

function setPropertyGroup(id: number) {
    data.updateProperty(props.property.id, props.property.name, id)
}

watch(() => props.property, () => {
    editName.value = false
    valuesOpen.value = false
})

</script>

<template>
    <div>
        <div class="prop-row" :class="{ selected: propertyVisible }" @click="toggleVisible">
            <PropertyIcon :type="props.property.type" class="prop-icon" />

            <template v-if="props.open">
                <input v-if="editName" ref="nameInput" type="text" class="prop-input" v-model="localName"
                    @click.stop @keyup.enter="renameProperty" @keyup.esc="cancelRename" @blur="renameProperty" />
                <span v-else class="prop-name">{{ props.property.name }}</span>

                <span v-if="props.property.mode == PropertyMode.id" class="prop-indicator">
                    <wTT :click="false" message="main.nav.properties.linked_property_tooltip">
                        <i class="bi bi-link-45deg"></i>
                    </wTT>
                </span>

                <div class="prop-actions" @click.stop>
                    <span v-if="props.property.type == PropertyType.tag || props.property.type == PropertyType.multi_tags"
                        class="prop-act" :class="{ active: valuesOpen }" @click="toggleValuesMenu">
                        <wTT v-if="valuesOpen" message="main.nav.properties.collapse_property_tooltip">
                            <i class="bi bi-chevron-down"></i>
                        </wTT>
                        <wTT v-else message="main.nav.properties.expand_property_tooltip">
                            <i class="bi bi-chevron-right"></i>
                        </wTT>
                    </span>
                    <span v-if="isTag(props.property.type)" class="prop-act"
                        @click="panoptic.showModal(ModalId.TAG, { propId: props.property.id })">
                        <wTT :click="false" message="main.nav.properties.open_tags">
                            <i class="bi bi-arrows-fullscreen"></i>
                        </wTT>
                    </span>
                    <span v-if="property.id != PropertyID.folders" class="prop-act" :class="{ active: isInFilter }"
                        @click="setFilter">
                        <wTT :click="false" message="main.menu.filters"><i class="bi bi-funnel-fill"></i></wTT>
                    </span>
                    <span class="prop-act" :class="{ active: isInSort }" @click="setSort">
                        <wTT :click="false" message="main.menu.sort.title"><i class="bi bi-sort-down"></i></wTT>
                    </span>
                    <span class="prop-act" :class="{ active: isInGroups }" @click="setGroup">
                        <wTT :click="false" message="main.menu.groupby"><i class="bi bi-collection"></i></wTT>
                    </span>
                    <Dropdown @click.prevent.stop="">
                        <template #button><span class="prop-act"><i class="bi bi-three-dots"></i></span></template>
                        <template #popup="{ hide }">
                            <div class="p-1">
                                <div v-if="props.property.id >= 0" class="bb" @click="startRename(); hide();">
                                    {{ $t('main.menu.editName') }}
                                </div>
                                <div v-if="props.property.id >= 0" class="bb" @click="deleteProperty(); hide();">
                                    {{ $t("main.nav.properties.delete_property") }}
                                </div>
                            </div>
                        </template>
                    </Dropdown>
                </div>
            </template>
        </div>
        <div v-if="props.open && valuesOpen">
            <TagMenu :property="props.property" :can-create="true" :can-customize="true" :can-delete="true"
                :can-link="true" />
        </div>
    </div>
</template>

<style scoped>
.prop-row {
    display: flex;
    align-items: center;
    gap: 6px;
    min-height: 24px;
    padding: 0 var(--spacing-sm);
    white-space: nowrap;
    cursor: pointer;
}

.prop-row:hover {
    background-color: var(--hover-bg);
}

.prop-row.selected {
    background-color: rgba(38, 117, 191, 0.32);
}

.prop-icon {
    width: 16px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    font-size: 12px;
    color: var(--text-secondary);
}

.prop-name {
    flex: 1;
    min-width: 0;
    font-size: var(--font-size-xs);
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
}

.prop-input {
    flex: 1;
    min-width: 0;
    height: 18px;
    padding: 0 4px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    background-color: var(--bg-primary);
    font-size: var(--font-size-xs);
    color: var(--text-primary);
}

.prop-indicator {
    display: inline-flex;
    align-items: center;
    font-size: 12px;
    color: var(--text-tertiary);
    flex-shrink: 0;
}

.prop-actions {
    display: flex;
    align-items: center;
    gap: 1px;
    margin-left: auto;
    flex-shrink: 0;
}

.prop-act {
    width: 18px;
    height: 18px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    font-size: 12px;
    color: var(--text-tertiary);
    flex-shrink: 0;
    cursor: pointer;
    opacity: 0;
}

/* Reveal action icons on row hover; keep active (filter/sort/group) ones pinned. */
.prop-row:hover .prop-act,
.prop-act.active {
    opacity: 1;
}

.prop-act.active {
    color: var(--primary);
}

.prop-act:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}
</style>