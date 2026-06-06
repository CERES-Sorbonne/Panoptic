<script setup lang="ts">
import { PropertyGroupId, Property } from '@/data/models'
import { TabManager } from '@/core/TabManager'
import PropertyIcon from '../properties/PropertyIcon.vue'

const props = defineProps<{
    property: Property
    tab: TabManager
}>()

function toggleVisibility() {
    const isVisible = props.tab.state.visibleProperties[props.property.id] === true
    props.tab.setVisibleProperty(props.property.id, !isVisible)
}

</script>

<template>
    <div class="property-row" @click="toggleVisibility">
        <PropertyIcon :type="property.type" class="prop-icon" />
        <span class="prop-name">{{ property.name }}</span>
    </div>
</template>

<style scoped>
.property-row {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 24px;
    padding: 0 var(--spacing-sm);
    cursor: pointer;
    white-space: nowrap;
}

.property-row:hover {
    background-color: var(--hover-bg);
}

.prop-icon {
    flex-shrink: 0;
}

.prop-name {
    color: var(--text-primary);
    font-size: var(--font-size-xs);
    overflow: hidden;
    text-overflow: ellipsis;
}
</style>
