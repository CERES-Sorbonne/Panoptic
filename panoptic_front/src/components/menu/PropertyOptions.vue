<script setup lang="ts">
import { ModalId, Property, PropertyID, PropertyMode, PropertyType } from '@/data/models';
import { computed, ref, watch } from 'vue';
import PropertyIcon from '../properties/PropertyIcon.vue';
import wTT from '../tooltips/withToolTip.vue';
import TagMenu from '../tags/TagMenu.vue';
import { useProjectStore } from '@/data/projectStore';
import { Filter } from '@/core/FilterManager';
import { useDataStore } from '@/data/dataStore';
import { isTag } from '@/utils/utils';
import { usePanopticStore } from '@/data/panopticStore';
import { Dropdowns } from '@/data/dropdowns';
import { useI18n } from 'vue-i18n';

const { t } = useI18n(({ useScope: 'global' }))

const panoptic = usePanopticStore()
const project = useProjectStore()
const data = useDataStore()
const tabManager = project.getTabManager()

const props = defineProps<{
    property: Property,
    open?: boolean
}>()

const optionsOpen = ref(false)
const valuesOpen = ref(false)
const localName = ref('')

const fullHover = ref(false)

const tab = computed(() => project.getTab())
const propertyVisible = computed(() => tab.value.visibleProperties[props.property.id] == true)

const isInFilter = computed(() => tabManager.collection.filterManager.state.filter.filters.some((f) => !f.isGroup && (f as Filter).propertyId == props.property.id))
const isInGroups = computed(() => tabManager.collection.groupManager.state.groupBy.includes(props.property.id))
const isInSort = computed(() => tabManager.collection.sortManager.state.sortBy.includes(props.property.id))
const filterId = computed(() => {
    if (!isInFilter.value) return undefined
    return tabManager.collection.filterManager.state.filter.filters.find((f) => !f.isGroup && (f as Filter).propertyId == props.property.id).id
})
const filterManager = () => tabManager.collection.filterManager
const sha1Mode = computed(() => tabManager.getSha1Mode())

function toggleVisible() {
    if (propertyVisible.value) {
        tabManager.setVisibleProperty(props.property.id, false)
    } else {
        tabManager.setVisibleProperty(props.property.id, true)
    }
}

function toggleOptionsMenu() {
    if (!props.open) return
    if (optionsOpen.value) {
        optionsOpen.value = false
    } else {
        optionsOpen.value = true
        localName.value = props.property.name
    }
    valuesOpen.value = false
}

function toggleValuesMenu() {
    if (props.property.type != PropertyType.tag && props.property.type != PropertyType.multi_tags) {
        return
    }
    if (valuesOpen.value) {
        valuesOpen.value = false
    } else {
        valuesOpen.value = true
    }
    optionsOpen.value = false
}

function setSort() {
    if (!isInSort.value) {
        tabManager.collection.sortManager.setSort(props.property.id)
    } else {
        tabManager.collection.sortManager.delSort(props.property.id)
    }
    tabManager.collection.sortManager.update(true)
}

function setGroup() {
    if (!isInGroups.value) {
        tabManager.collection.groupManager.setGroupOption(props.property.id)
    } else {
        tabManager.collection.groupManager.delGroupOption(props.property.id)
    }
    tabManager.collection.groupManager.update(true)
}

function deleteProperty() {
    if (confirm(t('common.properties.delete') + ': ' + props.property.name + ' ?   ' + props.property.id))
        data.deleteProperty(props.property.id)
}

async function renameProperty() {
    if (localName.value == '') {
        return
    }
    await data.updateProperty(props.property.id, localName.value)
    toggleOptionsMenu()
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

watch(() => props.property, () => {
    optionsOpen.value = false
})

</script>

<template>
    <div :class="fullHover ? 'hover-light' : ''">
        <div class="d-flex flex-row">
            <template v-if="props.open">
                <div v-if="!optionsOpen" class="option-holder hover-light btn-icon" style="width: 150px;"
                    @click="toggleOptionsMenu">
                    <PropertyIcon :type="props.property.type" class="me-2 btn-icon" @mouseenter="fullHover = true"
                        @mouseleave="fullHover = false" />
                    <span>{{ props.property.name }}</span>
                </div>
            </template>
            <template v-else>
                <PropertyIcon :type="props.property.type" class="me-2" style="position: relative; top: 2px;"/>
            </template>
            <div v-if="optionsOpen && props.open" class="d-flex" style="width: 150px;">
                <div><i class="btn-icon me-1 bi bi-x-lg" style="padding: 2px;" @click="toggleOptionsMenu"
                        @mouseenter="fullHover = true" @mouseleave="fullHover = false" />
                </div>
                <div class="flex-grow-1">
                    <input v-if="props.property.id >= 0" style="position: relative; top: 1px;" type="text"
                        class="text-input" v-model="localName" @change="renameProperty" />
                    <span v-else style="padding-top: 1px;">
                        <PropertyIcon :type="props.property.type" class="me-2 btn-icon" />
                        <span>{{ props.property.name }}</span>
                    </span>
                </div>
            </div>
            <template v-if="props.open">
                <div v-if="isTag(props.property.type)" style="width: 20px; margin-top: 2px; cursor: pointer;"
                    class="text-center" @click="panoptic.showModal(ModalId.TAG, { propId: props.property.id })">
                    <wTT :click="false" message="main.nav.properties.open_tags">
                        <i class="bi bi-arrows-fullscreen"></i>
                    </wTT>
                </div>
                <div style="width: 20px; margin-top: 2px;" class="text-center">
                    <wTT v-if="props.property.mode == PropertyMode.id" :click="false"
                        message="main.nav.properties.linked_property_tooltip">
                        <i class="bi bi-link-45deg"></i>
                    </wTT>
                </div>
            </template>
            <div style="width: 20px; margin-top: 2px;" @click="toggleVisible" class="btn-icon text-center">
                <wTT v-if="sha1Mode && props.property.mode == PropertyMode.id"
                    message="main.nav.properties.hidden_property_tooltip">
                    <span class="bi bi-eye-slash" @click.stop=""></span>
                </wTT>
                <wTT pos="right" message="main.nav.properties.hide_property_tooltip" v-else>
                    <span :class="'bi bi-eye text-' + (propertyVisible ? 'primary' : 'secondary')"></span>
                </wTT>
            </div>
            <template v-if="props.open">
                <div class="text-center" style="width: 20px; margin-top: 2px;">
                    <div v-if="props.property.type == PropertyType.tag || props.property.type == PropertyType.multi_tags"
                        @click="toggleValuesMenu" style="cursor: pointer;">
                        <wTT v-if="valuesOpen" message="main.nav.properties.collapse_property_tooltip"><i
                                class="bi bi-chevron-down"></i></wTT>
                        <wTT v-else message="main.nav.properties.expand_property_tooltip"><i
                                class="bi bi-chevron-right"></i>
                        </wTT>
                    </div>
                </div>
            </template>
        </div>
        <div v-if="props.open">
            <div v-if="optionsOpen" class="ms-3 pt-1">
                <div v-if="property.id != PropertyID.folders" class="options hover-light"
                    :class="isInFilter ? ' text-primary' : ''" @click="setFilter">
                    <div>
                        <i class="bi bi-funnel-fill me-2"></i>{{ $t("main.menu.filters") }}
                    </div>
                </div>
                <div class="options hover-light" :class="isInSort ? ' text-primary' : ''" @click="setSort"><i
                        class="bi bi-filter me-2"></i>{{ $t("main.menu.sort.title") }}</div>
                <div class="options hover-light" :class="isInGroups ? ' text-primary' : ''" @click="setGroup"><i
                        class="bi bi-collection me-2"></i>{{ $t("main.menu.groupby") }}</div>
                <div v-if="props.property.id >= 0" class="options hover-light" @click="deleteProperty"><i
                        class="bi bi-trash me-2"></i>{{ $t("main.nav.properties.delete_property") }}</div>
            </div>
            <div v-else-if="valuesOpen">
                <!-- <TagProperty :data="props.property" /> -->
                <TagMenu :property="props.property" :can-create="true" :can-customize="true" :can-delete="true"
                    :can-link="true" />
            </div>
        </div>
    </div>
</template>

<style scoped>
.option-holder {
    border-radius: 3px;
    padding: 2px;

}

.options {
    padding: 3px;
    cursor: pointer;
}
</style>