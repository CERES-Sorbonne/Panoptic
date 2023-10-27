<script setup lang="ts">
import { Property, PropertyMode, PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';
import { computed, ref } from 'vue';
import PropertyIcon from '../properties/PropertyIcon.vue';
import TagProperty from '../properties/TagProperty.vue';
import { Filter } from '@/data/models';
import { availableOperators } from '@/data/models';
import { defaultOperator } from '@/utils/filter';
import wTT from '../tooltips/withToolTip.vue';


const props = defineProps({
    property: Object as () => Property
})

const opionsOpen = ref(false)
const valuesOpen = ref(false)
const localName = ref('')

const tab = computed(() => globalStore.tabs[globalStore.selectedTab])
const propertyVisible = computed(() => tab.value.data.visibleProperties[props.property.id] == true)

const isInFilter = computed(() => tab.value.data.filter.filters.some((f) => !f.isGroup && (f as Filter).propertyId == props.property.id))
const isInGroups = computed(() => tab.value.data.groups.includes(props.property.id))
const isInSort = computed(() => tab.value.data.sortList.some(s => s.property_id == props.property.id))

const sha1Mode = computed(() => globalStore.getTab().data.sha1Mode)

function toggleVisible() {
    if (propertyVisible.value) {
        delete tab.value.data.visibleProperties[props.property.id]
    } else {
        tab.value.data.visibleProperties[props.property.id] = true
    }
}

function toggleOptionsMenu() {
    if (opionsOpen.value) {
        opionsOpen.value = false
    } else {
        opionsOpen.value = true
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
    opionsOpen.value = false
}

function setFilter() {
    const filterGroup = globalStore.getTab().data.filter
    const index = filterGroup.filters.findIndex((f) => !f.isGroup && (f as Filter).propertyId == props.property.id)
    if (index >= 0) {
        filterGroup.filters.splice(index, 1)
    }
    else {
        filterGroup.filters.push({
            propertyId: props.property.id,
            operator: availableOperators(props.property.type)[0],
            value: defaultOperator(props.property.type),
            isGroup: false
        } as Filter)
    }
}

function setSort() {
    const sort = globalStore.getTab().data.sortList
    const index = sort.findIndex(f => f.property_id == props.property.id)
    if(index >= 0) {
        sort.splice(index, 1)
    }
    else {
        sort.push({
            property_id: props.property.id,
            ascending: true
        })
    }
}

function setGroup() {
    const groups = globalStore.getTab().data.groups
    const index = groups.indexOf(props.property.id)
    if(index >= 0) {
        groups.splice(index, 1)
    }
    else {
        globalStore.addGrouping(props.property.id)
    }
}

function deleteProperty() {
    if(confirm('Supprimer la propriété: ' + props.property.name + ' ?'))
        globalStore.deleteProperty(props.property.id)
}

function renameProperty() {
    if(localName.value == '') {
        return
    }
    globalStore.updateProperty(props.property.id, localName.value)
}

</script>

<template>
    <div>
        <div class="d-flex flex-row">
            <PropertyIcon :type="props.property.type" class="me-2 btn-icon" @click="toggleOptionsMenu" />
            <span class="flex-grow-1 clickable" @click="toggleOptionsMenu">
                <span v-if="!opionsOpen">{{ props.property.name }}</span>
                <span v-else><input style="position: relative; top: -1px;" type="text" class="text-input" v-model="localName" @click.prevent.stop="" @change="renameProperty"/></span>
            </span>
            <div style="width: 20px;" class="text-center">
                <i v-if="props.property.mode == PropertyMode.id" class="bi bi-link-45deg"></i>
            </div>
            <div style="width: 20px;" @click="toggleVisible" class="btn-icon text-center">
                <span v-if="sha1Mode && props.property.mode == PropertyMode.id" class="bi bi-eye-slash" @click.stop=""></span>
                <wTT pos="right" :icon="false" message="main.nav.properties.hide_property_tooltip" v-else>
                    <span :class="'bi bi-eye text-' + (propertyVisible ? 'primary' : 'secondary')"></span>
                </wTT>
            </div>
            <div class="text-center" style="width: 20px;">
                <div v-if="props.property.type == PropertyType.tag || props.property.type == PropertyType.multi_tags"
                    @click="toggleValuesMenu" style="cursor: pointer;">
                    <i v-if="valuesOpen" class="bi bi-chevron-down"></i>
                    <i v-else class="bi bi-chevron-right"></i>
                </div>
            </div>
        </div>
        <div>
            <div v-if="opionsOpen" class="ms-3 pt-1">
                <div class="options" :class="isInFilter ? ' text-primary' : ''" @click="setFilter"><i class="bi bi-funnel-fill me-2"></i>Filtrer</div>
                <div class="options" :class="isInSort ? ' text-primary' : ''" @click="setSort"><i class="bi bi-filter me-2"></i>Trier</div>
                <div class="options" :class="isInGroups ? ' text-primary' : ''" @click="setGroup"><i class="bi bi-collection me-2"></i>Grouper</div>
                <div v-if="props.property.id >= 0" class="options" @click="deleteProperty"><i class="bi bi-trash me-2"></i>Supprimer</div>
            </div>
            <div v-else-if="valuesOpen">
                <TagProperty :data="props.property" />
            </div>
        </div>
    </div>
</template>

<style scoped>
.options {
    padding: 3px;
    cursor: pointer;
}
</style>