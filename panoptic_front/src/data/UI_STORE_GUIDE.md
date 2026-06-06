# UI Store Architecture Guide

## Overview

The `uiStore` manages all UI-related state (panel sizes, visibility, scroll positions) separately from business logic. This enables:
- Persistent UI preferences across sessions
- Clean separation of concerns (layout vs. data)
- Automatic backend persistence through watchers

## Architecture

### Three Reactive State Objects

Each state object has its own dedicated watcher that automatically persists changes to the backend:

#### 1. `panelStates`
Controls visibility and visibility-related settings
```typescript
{
    leftPanelOpen: boolean      // Show/hide left panel
    rightPanelOpen: boolean     // Show/hide right panel
    showSplitView: boolean      // Toggle split vs. single pane mode
}
```

#### 2. `resizeStates`
Tracks component dimensions
```typescript
{
    splitRowSecondaryHeight: number      // Height of secondary pane in row splits
    splitColumnSecondaryWidth: number    // Width of secondary pane in column splits
}
```

#### 3. `scrollStates`
Remembers scroll positions
```typescript
{
    leftPanelScrollX: number
    leftPanelScrollY: number
    rightPanelScrollX: number
    rightPanelScrollY: number
}
```

## Usage Patterns

### Reading State

```typescript
const uiStore = useUiStore()

// Direct access
const isLeftOpen = uiStore.panelStates.leftPanelOpen

// In computed
const secondarySize = computed(() => uiStore.resizeStates.splitColumnSecondaryWidth)
```

### Updating State

```typescript
// Use typed setters for clarity
uiStore.setPanelState('leftPanelOpen', false)
uiStore.setResizeState('splitColumnSecondaryWidth', 250)
uiStore.setScrollState('leftPanelScrollY', 100)

// Or direct assignment (also triggers watcher)
uiStore.panelStates.rightPanelOpen = true
```

### In Templates

```vue
<template>
    <SplitLayout
        :hide-primary="!uiStore.panelStates.leftPanelOpen"
        :hide-secondary="!uiStore.panelStates.rightPanelOpen"
        :secondary-size="uiStore.resizeStates.splitColumnSecondaryWidth"
    >
        <template #primary>Left Content</template>
        <template #secondary>Right Content</template>
    </SplitLayout>
</template>
```

## Persistence

### How It Works

1. Each reactive state object has a watcher
2. When state changes, the watcher calls `apiSetUIData()` with a key
3. Changes are persisted to the backend with the current project
4. On app load, `uiStore.init()` calls `apiGetUIData()` for each key

### Backend Keys

- `panelStates` → stored with key `'panelStates'`
- `resizeStates` → stored with key `'resizeStates'`
- `scrollStates` → stored with key `'scrollStates'`

### Debouncing (Future)

If watchers trigger too frequently (e.g., during scroll), you can add debouncing:

```typescript
watch(() => scrollStates, debounce(async () => {
    await apiSetUIData(SCROLL_STATE_KEY, scrollStates)
}, 500), { deep: true })
```

## Integration with projectStore

The `uiStore` is initialized in `projectStore.init()`:

```typescript
const uiStore = useUiStore()
await Promise.all([
    dataStore.init(),
    mediaStore.init(),
    uiStore.init()
])
```

This ensures UI state is loaded when the project loads.

## Adding New UI State

To add a new UI state (e.g., `sidebarCollapsed`):

1. Add to the appropriate interface:
```typescript
export interface PanelStates {
    // ... existing fields
    sidebarCollapsed: boolean
}
```

2. Initialize in reactive:
```typescript
const panelStates = reactive<PanelStates>({
    // ... existing fields
    sidebarCollapsed: false
})
```

3. Use through store:
```typescript
uiStore.setPanelState('sidebarCollapsed', true)
```

The watcher automatically persists the change.

## Best Practices

### Do's
- ✓ Use setters for type safety: `setPanelState()`, `setResizeState()`, `setScrollState()`
- ✓ Keep UI state simple (booleans, numbers, basic objects)
- ✓ Initialize reasonable defaults
- ✓ Use computed properties for complex derived state
- ✓ Group related state in the appropriate reactive object

### Don'ts
- ✗ Don't store business logic state (use `projectStore`, `dataStore`, etc.)
- ✗ Don't store complex nested objects without understanding watchers
- ✗ Don't directly import/use other stores inside uiStore
- ✗ Don't manually call `apiSetUIData()` (watchers handle it)

## Common Scenarios

### Toggle a Panel

```typescript
function toggleRightPanel() {
    uiStore.setPanelState('rightPanelOpen', !uiStore.panelStates.rightPanelOpen)
}
// Watcher automatically saves to backend
```

### Handle Resize Event

```typescript
function handleResize(newSize: number) {
    uiStore.setResizeState('splitColumnSecondaryWidth', newSize)
}
// Watcher automatically saves to backend
```

### Remember Scroll Position on Unmount

```typescript
onBeforeUnmount(() => {
    uiStore.setScrollState('leftPanelScrollY', leftPanel.value?.scrollTop ?? 0)
})
// Watcher automatically saves to backend
```

### Load Scroll Position on Mount

```typescript
onMounted(() => {
    leftPanel.value?.scrollTo(0, uiStore.scrollStates.leftPanelScrollY)
})
```

## Testing

When testing components that use `uiStore`:

```typescript
it('respects panel visibility from uiStore', () => {
    const uiStore = useUiStore()
    uiStore.setPanelState('rightPanelOpen', false)
    
    const { queryByTestId } = render(MyComponent)
    expect(queryByTestId('right-panel')).toBeNull()
})
```

Mock the store methods if needed:

```typescript
vi.mocked(apiSetUIData).mockResolvedValue(undefined)
```
