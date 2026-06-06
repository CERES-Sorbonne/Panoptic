# FolderPanel Reimplementation Plan

## Goal
Replace dummy data in `FolderPanel.vue` with real folder tree from the store, using the same simple flat-style rendering (not the complex styled tree in FolderList2).

## Files to Create/Modify

### 1. NEW: `src/components/FolderTree/FolderList.vue`
A recursive component that renders a list of folders with:
- **Data source**: `useDataStore()` -> `data.folders` (FolderIndex)
- **Props**: `folders: Folder[]`, `filterManager?: FilterManager`, `tab?: TabManager`, `depth?: number`
- **Features**:
  - Expand/collapse children (visibility state tracked locally)
  - Click to select/deselect folders (integrates with FilterManager + TabManager like FolderList2)
  - Shows folder count next to name
  - Hover-revealed option dropdown (FolderOptionDropdown)
  - Recursive rendering of children at increased depth

### 2. MODIFY: `src/components/layoutpanels/FolderPanel.vue`
- Remove the hardcoded `folderTree` array
- Import and use new `FolderList` component
- Pass root folders to FolderList: extract folders where `parent === 0 || parent === undefined` from `data.folders`
- Wire up FilterManager and TabManager for selection to work

## Implementation Details

### FolderList.vue structure
- Uses `useDataStore()` for folder data
- Props: folders, filterManager (optional), tab (optional), depth (default 0)
- `isSelected` computed from filterManager.state.folders
- `toggleSelect()` logic mirrors FolderList2 (handles parent/child selection)
- Render: tree-node div with caret, icon, label, count, option dropdown
- Recursive `<FolderList>` for children when expanded

### FolderPanel.vue changes
- Remove hardcoded `folderTree` array
- Import and use new `FolderList` component
- Extract root folders: `Object.values(data.folders).filter(f => !f.parent || f.parent === 0)`
- Wire up FilterManager and TabManager for selection

## Key Design Decisions
1. **Reuse existing CSS** - Same `.tree-node`, `.tree-caret`, `.tree-icon`, `.tree-label` classes
2. **Recursive but simple** - Recursive components, flat-style rendering (no tree lines like FolderList2)
3. **Selection integration** - When filterManager/tab provided, click selects/deselects with parent/child logic from FolderList2
4. **Count display** - Shows `folder.count` aligned to the right

## Bug Fix Needed
- **FolderPanel.vue:30** - `tab.value` should be just `tab`. Computed refs auto-unwrap in Vue 3 templates, so accessing `.value` tries to read `TabManager.value` which is undefined.
  - Change: `tab.value?.collection.filterManager` → `tab?.collection.filterManager`
  - Change: `tab.value` → `tab`
