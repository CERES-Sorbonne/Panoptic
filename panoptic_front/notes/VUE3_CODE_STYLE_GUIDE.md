# Vue 3 Frontend Code Style Guide

## Overview
This guide documents the code style conventions used in the Panoptic Vue3 frontend. The project uses TypeScript with the Composition API and script setup syntax, organized with Pinia stores for state management.

---

## Script Structure

### Setup Block
- **Always use** `<script setup lang="ts">` syntax
- This enables implicit component registration and simpler code

```vue
<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useStore } from '@/data/store'

const store = useStore()
</script>
```

---

## Imports

### Path Aliases
- Use the `@/` alias for all internal imports (configured in tsconfig.json)
- Keeps imports consistent and makes refactoring easier

```typescript
// ✓ Good
import { useTabStore } from '@/data/tabStore'
import PropertyModal from '@/components/modals/PropertyModal.vue'
import { objValues } from '@/utils/utils'

// ✗ Avoid
import { useTabStore } from '../data/tabStore'
import PropertyModal from '../../../components/modals/PropertyModal.vue'
```

### Import Organization
1. Vue imports (from 'vue')
2. Library imports (third-party packages)
3. Internal imports (stores, components, utilities)

---

## Props and Emits

### Props Definition
- Use `defineProps<>()` with TypeScript type syntax for type inference
- Use `withDefaults()` when providing default values

```typescript
const props = defineProps<{
    id?: string
    maxWidth?: number
    layer?: number
}>()

// With defaults
const props = withDefaults(defineProps<{
    id: ModalId
    layer?: number
    maxHeight?: number
}>(), {
    layer: 0
})
```

### Emits Definition
- Use `defineEmits()` to declare emitted events
- Use `defineExpose()` to explicitly expose methods to parent components

```typescript
const emits = defineEmits(['resize', 'show', 'hide'])

defineExpose({
    hide
})
```

---

## Reactive State

### Creating Reactive Variables
- Use `ref()` for primitive values and single objects
- Use `reactive()` for complex reactive objects (less common)
- Use `computed()` for derived state

```typescript
const show = ref(false)
const elem = ref(null)

const available = computed(() => {
    return items.value.filter(i => i.active)
})

const localDefaults = reactive({
    similar: undefined,
    group: undefined,
    execute: undefined
})
```

### Store Integration
- Initialize stores at the top of the script
- Stores are Pinia stores, use them directly in templates and script

```typescript
const tabStore = useTabStore()
const panoptic = usePanopticStore()

// Access store data
const tab = tabStore.getTab(props.id)
panoptic.hideModal(props.id)
```

---

## Lifecycle and Watchers

### Lifecycle Hooks
- Use `onMounted()` for initialization
- Use `watch()` for reactive updates

```typescript
onMounted(() => {
    window.addEventListener('resize', onWindowResize)
    modal.registerModal(props.id, props.layer)
})

watch(() => props.id, async () => {
    show.value = false
    await nextTick()
    loadTab()
})
```

### Watching Reactive Objects
- Watch computed properties or refs to trigger updates
- Use async when needed

```typescript
watch(() => actions.defaultActions, updateLocal)

watch(() => modal.openIndex[props.id], (newVal, oldVal) => {
    if (newVal) {
        show()
    }
})
```

---

## Template

### Directives
- Use `v-if` for conditional rendering
- Use `v-for` for lists (always provide a key)
- Use `v-model` for two-way binding
- Use `@event` for event binding

```vue
<template>
    <div v-if="show && tabStore.loaded">
        <div v-for="item in items" :key="item.id">
            {{ item.name }}
        </div>
        <input v-model="searchText" />
        <button @click="handleClick">Click</button>
    </div>
</template>
```

### Class and Style Binding
- Use `:class` for dynamic classes
- Use inline `:style` for computed styles
- Prefer CSS classes when possible

```vue
<div :class="titleStyle" class="container">
    <div :style="{ width: width + 'px', height: height + 'px' }">
        Content
    </div>
</div>
```

### Bootstrap Utility Classes
- The project uses Bootstrap 5, leverage its utility classes
- Common utilities: `d-flex`, `flex-grow-1`, `m-2`, `me-3`, `p-4`, etc.

```vue
<div class="d-flex justify-content-center align-items-center">
    <div class="flex-grow-1">Left</div>
    <button class="base-btn me-3">Button</button>
</div>
```

### Slots
- Use named slots for complex layouts
- Provide slot scope when passing data

```vue
<slot name="title"></slot>
<slot name="content" :data="data" :width="modalWidth" :height="modalHeight"></slot>
```

---

## Styling

### Scoped Styles
- Always use `<style scoped>` to prevent style leakage
- Minimal inline styles; use classes instead

```vue
<style scoped>
.container {
    padding: 1rem;
    border: var(--hr);
    border-radius: 0.4rem;
}

.title {
    background-color: rgb(238, 238, 255);
    padding: 4px;
}
</style>
```

### CSS Custom Properties
- All theme and color variables are defined in `src/assets/theme.css`
- Import this file in components that need theme-aware styling
- Use CSS custom properties for all colors, spacing, and sizing

**Available Color Variables:**
- Primary: `--primary`, `--primary-light`, `--primary-dark`
- Backgrounds: `--bg-primary`, `--bg-secondary`, `--bg-tertiary`
- Text: `--text-primary`, `--text-secondary`, `--text-tertiary`, `--text-inverse`
- Borders: `--border-color`, `--border-light`, `--border-dark`
- Status: `--success`, `--error`, `--warning`, `--info`

**Available Spacing Variables:**
- `--spacing-xs` through `--spacing-2xl`
- `--radius-sm` through `--radius-xl`

**See `src/assets/theme.css` for the complete list of available variables.**

### Theme
- The application uses a **light theme** inspired by **PyCharm Island Light**
- Clean, light backgrounds (#ffffff, #f5f5f5) with excellent contrast
- Professional blue accent color (#1678c2) for primary actions
- All theme values are centralized in `src/assets/theme.css` for consistency

---

## Naming Conventions

### Files
- **Components**: PascalCase (e.g., `TabContainer.vue`, `PropertyModal.vue`)
- **Views**: PascalCase ending with View (e.g., `MainView.vue`, `PanopticView.vue`)
- **Stores**: camelCase ending with Store (e.g., `tabStore.ts`, `panopticStore.ts`)
- **Utilities**: camelCase (e.g., `utils.ts`, `keyState.ts`)

### Variables and Functions
- **Variables**: camelCase (`const showModal = ref(false)`)
- **Constants**: UPPER_SNAKE_CASE for module-level constants
- **Functions**: camelCase (`function handleClick() {}`)
- **Classes**: PascalCase
- **Booleans**: Prefix with `is` or `has` when possible (`isActive`, `hasError`)

---

## Code Organization Pattern

### Typical Component Structure
```typescript
// 1. Imports
import { ref, computed, watch, onMounted } from 'vue'
import { useStore } from '@/data/store'

// 2. Props
const props = defineProps<{
    id: string
}>()

// 3. Emits
const emits = defineEmits(['update'])

// 4. Store initialization
const store = useStore()

// 5. Reactive state (ref/reactive)
const show = ref(false)
const state = reactive({
    count: 0
})

// 6. Computed
const data = computed(() => store.getData())

// 7. Functions/Methods
function handleClick() {
    // ...
}

function updateData() {
    // ...
}

// 8. Lifecycle & Watchers
onMounted(() => {
    // Initialize
})

watch(() => props.id, () => {
    // React to changes
})

// 9. Expose (if needed)
defineExpose({ hide })
```

---

## Common Patterns

### Modal Components
- Extend Modal2.vue base component
- Use ModalId enum for identification
- Provide title and content slots

```vue
<script setup lang="ts">
import Modal2 from './Modal2.vue'
import { ModalId } from '@/data/models'

const props = defineProps<{
    id: ModalId
}>()
</script>

<template>
    <Modal2 :id="props.id">
        <template #title>Modal Title</template>
        <template #content="{ data, width, height }">
            <!-- Content here -->
        </template>
    </Modal2>
</template>
```

### Container Components with Slot Props
- Provide context through slot scope
- Common for wrapper components

```vue
<template>
    <div v-if="show" :style="{ width, height }">
        <slot :data="data" :width="width" :height="height" :hide="close"></slot>
    </div>
</template>
```

### Layout Components (Layout/Presentation Separation)
Layout components are pure structural containers that orchestrate content without handling data or business logic. This pattern separates layout concerns from feature logic, improving reusability and maintainability.

**Key Principles:**
- Layout components are "blind" to content — they only care about positioning and structure
- Never import stores, fetch data, or perform calculations
- Accept only layout-related props: `width`, `height`, `direction`, `spacing`, `gap`, etc.
- Use named slots or slot props for flexible content placement
- Feature components are composed inside layout components by parent/view components

**File Structure:**
```
src/
├── layouts/                      # Pure layout orchestration
│   ├── TwoColumnLayout.vue      # Grid-based two-column layout
│   ├── TabPanelLayout.vue       # Tab switching + content area
│   └── SidebarLayout.vue        # Sidebar + main content
│
├── views/                        # Page composition (connects layout + data)
│   ├── MainView.vue            # Orchestrates layouts and feature components
│   └── PanopticView.vue        # Gets data from stores, passes to layouts
│
└── components/                   # Feature components (logic + display)
    ├── properties/
    └── filters/
```

**Layout Component Example:**
```vue
<script setup lang="ts">
interface Props {
    leftWidth?: number    // Layout props only
    gap?: number
    resizable?: boolean
}

withDefaults(defineProps<Props>(), {
    leftWidth: 300,
    gap: 16,
    resizable: true
})
</script>

<template>
    <div class="d-flex" :style="{ gap: gap + 'px' }">
        <div class="left-panel" :style="{ width: leftWidth + 'px' }">
            <slot name="left"></slot>
        </div>
        <div class="right-panel flex-grow-1">
            <slot name="right"></slot>
        </div>
    </div>
</template>

<style scoped>
.left-panel {
    overflow-y: auto;
}

.right-panel {
    overflow-y: auto;
}
</style>
```

**View Component Example (connects layout + data):**
```vue
<script setup lang="ts">
import { useStore } from '@/data/store'
import TwoColumnLayout from '@/layouts/TwoColumnLayout.vue'
import PropertyList from '@/components/properties/PropertyList.vue'
import PropertyDetail from '@/components/properties/PropertyDetail.vue'

const store = useStore()
const selectedId = computed(() => store.selectedPropertyId)
</script>

<template>
    <TwoColumnLayout :left-width="400" :gap="12">
        <template #left>
            <PropertyList @select="store.selectProperty" />
        </template>
        <template #right>
            <PropertyDetail v-if="selectedId" :id="selectedId" />
        </template>
    </TwoColumnLayout>
</template>
```

**Benefits:**
- ✓ Layout changes are isolated from feature logic
- ✓ Layouts are easily reusable across different content
- ✓ Clearer data flow: stores → views → layouts → feature components
- ✓ Layout components are simpler to test and reason about
- ✓ UI/design changes don't require touching business logic

---

## UI State Management (uiStore)

The application uses a dedicated `uiStore` to manage all UI-related state separately from business logic. This enables:
- Persistent UI preferences (panel sizes, visibility, scroll positions)
- Clean separation between layout and data logic
- Automatic backend persistence through watchers

### Structure

The `uiStore` has three main reactive objects, each with its own watcher:

```typescript
// Panel visibility states
panelStates: {
    leftPanelOpen: boolean
    rightPanelOpen: boolean
    showSplitView: boolean
}

// Resize/dimension states
resizeStates: {
    splitRowSecondaryHeight: number      // For row splits
    splitColumnSecondaryWidth: number    // For column splits
}

// Scroll position states
scrollStates: {
    leftPanelScrollX: number
    leftPanelScrollY: number
    rightPanelScrollX: number
    rightPanelScrollY: number
}
```

### Usage Pattern

**In a View Component:**
```typescript
const uiStore = useUiStore()

// Read state
const secondarySize = computed({
    get: () => uiStore.resizeStates.splitColumnSecondaryWidth,
    set: (value) => uiStore.setResizeState('splitColumnSecondaryWidth', value)
})

// Call setters when UI events happen
function handleResize(newSize: number) {
    uiStore.setResizeState('splitColumnSecondaryWidth', newSize)
}

// Toggle panel visibility
function togglePanel() {
    uiStore.setPanelState('rightPanelOpen', !uiStore.panelStates.rightPanelOpen)
}
```

### Initialization

The uiStore must be initialized when the project loads:

```typescript
// In projectStore init()
const uiStore = useUiStore()
await uiStore.init()  // Loads persisted UI state from backend
```

### Key Principles

- **One watcher per reactive state**: Changes to panelStates, resizeStates, and scrollStates are watched independently
- **Automatic persistence**: Each watcher automatically saves changes to backend via `apiSetUIData`
- **Type-safe setters**: Use `setPanelState()`, `setResizeState()`, `setScrollState()` for type safety
- **Deep watching**: All state objects use `{ deep: true }` to watch nested changes

---

## Layout Components (Pure Layout Pattern)

Layout components are structural containers that orchestrate content without handling data or business logic. This pattern separates layout concerns from feature logic, improving reusability and maintainability.

### Principles

**Layout components are "blind" to content:**
- Never import stores or fetch data
- Only accept layout-related props (size, direction, gap, resizable)
- Only emit layout-related events (@resize, etc)
- Use slots to accept arbitrary content

**View components connect layout + state:**
- Import uiStore for UI state
- Map uiStore reactive state to layout props
- Import and compose feature components
- Translate layout events to uiStore updates

**Feature components handle data:**
- Import stores for business logic
- Have no knowledge of layout structure
- Focus on their specific domain

### File Organization

```
src/
├── layouts/                      # Pure layout components
│   ├── SplitLayout.vue          # Resizable split (row/column)
│   ├── AppShellLayout.vue       # App-level structure
│   └── IslandPanel.vue          # Floating/modal panel layout
│
├── views/                        # View layer (connects layout + data)
│   ├── MainView.vue            # Orchestrates layouts + stores
│   └── PanopticView.vue        # Page composition
│
└── components/                   # Feature components (data-aware)
    ├── properties/              # Property management
    └── filters/                 # Filter logic
```

### Example: Using SplitLayout with uiStore

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useUiStore } from '@/data/uiStore'
import SplitLayout from '@/layouts/SplitLayout.vue'
import LeftPanel from '@/components/LeftPanel.vue'
import RightPanel from '@/components/RightPanel.vue'

const uiStore = useUiStore()

const secondarySize = computed({
    get: () => uiStore.resizeStates.splitColumnSecondaryWidth,
    set: (value) => uiStore.setResizeState('splitColumnSecondaryWidth', value)
})
</script>

<template>
    <SplitLayout
        direction="column"
        :secondary-size="secondarySize"
        :hide-secondary="!uiStore.panelStates.rightPanelOpen"
        resizable
    >
        <template #primary>
            <LeftPanel />
        </template>
        <template #secondary>
            <RightPanel />
        </template>
    </SplitLayout>
</template>
```

### Benefits

- ✓ Layout changes don't affect business logic
- ✓ Layouts are reusable across different content
- ✓ UI preferences persist across sessions
- ✓ Clearer data flow and component responsibilities
- ✓ Easier to test (layout props/events are predictable)
- ✓ UI state is centralized in uiStore

### Common Layout Components

**SplitLayout** — Resizable split pane (primary + secondary)
- Props: `direction`, `secondarySize`, `resizable`, `minPrimary`, `minSecondary`, `hidePrimary`, `hideSecondary`, `gap`
- Slots: `primary`, `secondary`
- Events: (none currently, but can be extended)

**AppShellLayout** — Top-level app structure
- Contains header, sidebar, main content area
- Typically used in the root App.vue

**IslandPanel** — Floating panel layout
- For modal-like panels that float over content

---

## TypeScript Usage

### Type Definitions
- Use explicit types for props and state
- Leverage TypeScript for better IDE support and type safety

```typescript
const props = defineProps<{
    items: Item[]
    onSelect: (item: Item) => void
}>()

interface LocalState {
    selected: Item | null
    loading: boolean
}

const state = reactive<LocalState>({
    selected: null,
    loading: false
})
```

### Strict Mode Settings
- Project has `strict: true` in tsconfig
- `strictNullChecks: false` (less strict null checking)
- `noImplicitAny: false` (allow implicit any where needed)

---

## Best Practices

### Do's
- ✓ Keep components focused and single-purpose
- ✓ Use meaningful variable names
- ✓ Extract computed properties for complex logic
- ✓ Use Bootstrap utility classes for layout
- ✓ Leverage CSS custom properties for theming
- ✓ Keep template logic simple
- ✓ Use TypeScript for type safety

### Don'ts
- ✗ Don't use unscoped styles (always use `scoped`)
- ✗ Don't directly mutate props
- ✗ Don't over-comment; code should be self-explanatory
- ✗ Don't mix relative and absolute imports
- ✗ Don't create overly complex computed properties
- ✗ Don't forget keys in v-for loops
- ✗ Don't inline complex styles; use CSS classes

---

## Additional Resources

- **Vue 3 Docs**: https://vuejs.org/
- **Pinia**: State management library
- **TypeScript**: Type safety for JavaScript
- **Bootstrap 5**: CSS framework for utilities and components
- **Vite**: Build tool and dev server

---

## Notes

- The project uses a **light theme** with the **PyCharm Island Light** palette as the target for the UI refactor
- Components are organized by type (components, views, modals)
- Stores manage global application state using Pinia
- Consistent use of path aliases makes code more maintainable
- Dark theme CSS in the current codebase is unused and should be removed/updated during the refactor
