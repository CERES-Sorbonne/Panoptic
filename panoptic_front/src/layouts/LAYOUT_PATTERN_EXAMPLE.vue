<!--
  EXAMPLE: How to use SplitLayout with uiStore

  This demonstrates the layout + state separation pattern:
  - SplitLayout is pure layout (no data logic)
  - uiStore manages UI state (panel sizes, visibility)
  - View component connects them together
  - Each reactive state in uiStore has its own watcher for persistence
-->

<script setup lang="ts">
import { useUiStore } from '@/data/uiStore'
import SplitLayout from '@/layouts/SplitLayout.vue'
import PropertyList from '@/components/properties/PropertyList.vue'
import PropertyDetail from '@/components/properties/PropertyDetail.vue'

const uiStore = useUiStore()

// Use panelStates to control visibility
const showPrimary = computed(() => !uiStore.panelStates.leftPanelOpen)
const showSecondary = computed(() => uiStore.panelStates.rightPanelOpen)

// Use resizeStates for layout dimensions (changes are auto-saved to backend)
const secondarySize = computed({
    get: () => uiStore.resizeStates.splitColumnSecondaryWidth,
    set: (value) => uiStore.setResizeState('splitColumnSecondaryWidth', value)
})

// Handle resize events from layout
function handleResize(newSize: number) {
    secondarySize.value = newSize
}
</script>

<template>
    <SplitLayout
        direction="column"
        :secondary-size="secondarySize"
        :hide-primary="showPrimary"
        :hide-secondary="!showSecondary"
        resizable
        @resize="handleResize"
    >
        <template #primary>
            <!-- Data-aware component from @src/components -->
            <PropertyList />
        </template>

        <template #secondary>
            <!-- Another data-aware component -->
            <PropertyDetail />
        </template>
    </SplitLayout>
</template>

<!--
  KEY PATTERN RULES:

  1. Layout components (SplitLayout) are PURE:
     - Only accept layout props (size, direction, gap, resizable)
     - Only emit layout events (@resize, etc)
     - No imports from @/data stores
     - No business logic

  2. UI State (uiStore) manages:
     - Panel visibility (panelStates)
     - Panel sizes (resizeStates)
     - Scroll positions (scrollStates)
     - Each state is watched and auto-persisted to backend

  3. View components (like this one) connect them:
     - Import uiStore
     - Map uiStore state to layout props
     - Map layout events to uiStore updates
     - Import and compose feature components

  4. Feature components (@src/components) are data-aware:
     - Handle business logic
     - Import stores as needed
     - Never know about layout structure
-->
