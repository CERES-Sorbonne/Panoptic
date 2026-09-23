# PropertyPanel Reimplementation Plan

## Goal
Replace dummy data in `PropertyPanel.vue` with real property groups from the store, using the same rendering style as Menu.vue's PropertyGroup.

## Files to Create/Modify

### 1. NEW: `src/components/layoutpanels/PropertyGroupPanel.vue`
A component that renders property groups (simplified version of PropertyGroup from Menu):

**Props**:
- `tab: TabManager` - required for visibility toggling and filter/sort/group actions

**Data source**:
- `useDataStore()` -> `data.propertyTree` (array of PropertyGroupNode), `data.properties`, `data.propertyGroups`

**Features**:
- Renders each group from `data.propertyTree` (skip footer groups - last 2 items)
- Expandable/collapsible group headers showing group name
- Lists properties within each group with PropertyIcon and property name
- Click to toggle visibility (uses `tab.setVisibleProperty()`)
- Eye icon showing visibility state (all/none visible)

**Structure**:
```vue
<script setup>
// Props: tab: TabManager
// Uses useDataStore() for data.propertyTree, data.properties, data.propertyGroups
// groupOpen state: reactive object tracking which groups are expanded

const groupOpen = reactive({})
const data = useDataStore()

// Visible groups: skip last 2 (footer placeholders)
const visibleGroups = computed(() => data.propertyTree.slice(0, -2))

// Get group name from propertyGroups[groupId]
function getGroupName(groupId) {
    if (groupId === PropertyGroupId.DEFAULT) return 'Default'
    if (groupId === PropertyGroupId.METADATA) return t('common.properties.metadata')
    return data.propertyGroups[groupId]?.name ?? 'Unknown'
}

// Check if all properties in group are visible
function isAllVisible(node) {
    return node.propertyIds.every(id => tab.isVisibleProperty(id))
}

// Toggle visibility for all properties in a group
function toggleGroupVisibility(node) { ... }

// Expand/collapse group
function toggleExpand(groupId) { ... }
</script>

<template>
    <div v-for="node in visibleGroups" :key="node.groupId">
        <!-- Group header -->
        <div class="group-header" @click="toggleExpand(node.groupId)">
            <span class="expand-icon">{{ groupOpen[node.groupId] ? '▾' : '▸' }}</span>
            <span class="group-name">{{ getGroupName(node.groupId) }}</span>
            <span class="visibility-toggle" @click.stop="toggleGroupVisibility(node)">
                <i :class="'bi bi-eye' + (isAllVisible(node) ? ' text-primary' : ' text-secondary')"></i>
            </span>
        </div>
        <!-- Properties in group -->
        <template v-if="groupOpen[node.groupId]">
            <PropertyRow 
                v-for="propId in node.propertyIds" 
                :key="propId"
                :property="data.properties[propId]" 
                :tab="tab" 
            />
        </template>
    </div>
</template>

<style scoped>
.group-header { ... }
.expand-icon { ... }
.group-name { ... }
.visibility-toggle { ... }
</style>
```

### 2. NEW: `src/components/layoutpanels/PropertyRow.vue`
A component for individual property rows within a group:

**Props**:
- `property: Property` - the property to display
- `tab: TabManager` - for visibility toggling

**Features**:
- Shows PropertyIcon + property name
- Click to toggle visibility
- Hover reveals option menu (rename/delete - optional, can be added later)

**Structure**:
```vue
<script setup>
// Props: property: Property, tab: TabManager
const data = useDataStore()

function toggleVisibility() {
    const isVisible = tab.state.visibleProperties[property.id] === true
    tab.setVisibleProperty(property.id, !isVisible)
}
</script>

<template>
    <div class="property-row" @click="toggleVisibility">
        <PropertyIcon :type="property.type" class="prop-icon" />
        <span class="prop-name">{{ property.name }}</span>
    </div>
</template>

<style scoped>
.property-row { ... }
.prop-icon { ... }
.prop-name { ... }
</style>
```

### 3. MODIFY: `src/components/layoutpanels/PropertyPanel.vue`
- Remove dummy `properties` and `exportFormats` arrays  
- Import TabContainer, PropertyGroupPanel
- Wrap in TabContainer to get current tab (like Menu.vue)
- Keep the IslandPanel structure and header styling

**Changes**:
```vue
<script setup>
import TabContainer from '@/components/TabContainer.vue'
import PropertyGroupPanel from './PropertyGroupPanel.vue'
// Remove: properties array, exportFormats array, IslandPanel import stays

import { useTabStore } from '@/data/tabStore'
const tabStore = useTabStore()
</script>

<template>
    <IslandPanel grow>
        <template #header>
            <!-- unchanged header -->
        </template>
        <div class="tw-body">
            <TabContainer :id="tabStore.mainTab">
                <template #default="{ tab }">
                    <PropertyGroupPanel :tab="tab" />
                </template>
            </TabContainer>
        </div>
    </IslandPanel>
</template>

<!-- CSS: keep tw-header, tw-body styles; remove prop-row/export-row styles -->
```

## Key Design Decisions
1. **Reuse TabContainer** - Same pattern as Menu.vue for getting current tab context via slot
2. **Simplified PropertyGroup** - No drag-drop (only needed in menu), just display + toggle visibility
3. **Group filtering** - Skip footer groups (last 2 items in propertyTree) and show real named groups from `data.propertyGroups`
4. **Same styling pattern** - Uses tw-header/tw-body like FolderPanel, group/property styles similar to Menu.vue PropertyGroup
5. **PropertyRow as separate component** - Clean separation, can be extended with options later

## Notes
- PropertyPanel uses TabContainer which handles the tab lifecycle properly (shows content only when tab is loaded)
- PropertyGroupPanel should guard against empty propertyTree - add `v-if` or check in computed
