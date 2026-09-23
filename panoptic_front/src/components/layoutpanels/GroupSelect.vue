<script setup lang="ts">
import PropertyValue from '@/components/properties/PropertyValue.vue'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
import { Group } from '@/core/GroupManager'
import { PropertyValue as PropertyValueModel } from '@/data/models'
import { getGroupParents } from '@/utils/utils'

const props = defineProps<{
    groups: Group[]
    selected: Group | null
}>()

const emit = defineEmits<{
    (e: 'select', group: Group): void
}>()

function groupLabel(g: Group) {
    const values: PropertyValueModel[] = []
    getGroupParents(g).reverse().forEach(p => values.push(...(p.meta.propertyValues ?? [])))
    values.push(...(g.meta.propertyValues ?? []))
    return values
}
</script>

<template>
    <Dropdown v-if="groups.length" placement="bottom-start">
        <template #button>
            <div class="group-select-button">
                <template v-if="selected">
                    <template v-for="(value, index) in groupLabel(selected)" :key="index">
                        <PropertyValue :value="value" />
                        <div v-if="index < groupLabel(selected).length - 1" class="separator"></div>
                    </template>
                </template>
                <i class="bi bi-chevron-down ms-1"></i>
            </div>
        </template>
        <template #popup="{ hide }">
            <div class="group-select-popup">
                <div
                    v-for="g in groups"
                    :key="g.id"
                    class="group-select-item"
                    :class="{ 'is-selected': selected && g.id === selected.id }"
                    @click="emit('select', g); hide()"
                >
                    <template v-for="(value, index) in groupLabel(g)" :key="index">
                        <PropertyValue :value="value" />
                        <div v-if="index < groupLabel(g).length - 1" class="separator"></div>
                    </template>
                    <span class="text-secondary ms-1">({{ g.slots.length }})</span>
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.group-select-button {
    display: inline-flex;
    align-items: center;
    padding: 0px 2px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    cursor: pointer;
    color: var(--text-secondary);
    transition: background-color var(--transition-fast);
    min-height: 24px;
    /* the popup renders at 14px; without this the button inherits the ambient 16px and its chip
       comes out taller than the same chip in the options */
    font-size: 14px;
}

.group-select-button:hover {
    background-color: var(--hover-bg);
}

.group-select-popup {
    display: flex;
    flex-direction: column;
    max-height: 400px;
    overflow-y: auto;
}

.group-select-item {
    display: inline-flex;
    align-items: center;
    padding: 4px 8px;
    cursor: pointer;
    white-space: nowrap;
    transition: background-color var(--transition-fast);
}

.group-select-item:hover {
    background-color: var(--hover-bg);
}

.group-select-item.is-selected {
    color: var(--primary);
    font-weight: var(--font-weight-medium);
}

.separator {
    border-left: 2px solid var(--border-color);
    margin: 3px 4px;
}
</style>
