<script setup lang="ts">
import { computed } from 'vue'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
import { TabManager } from '@/core/TabManager';
import { CollectionManager } from '@/core/CollectionManager';

const props = defineProps<{
    tab: TabManager
    collection?: CollectionManager
}>()

const collection = computed(() => props.collection ?? props.tab.collection)

function updateSha1Mode(value: boolean) {
    collection.value.groupManager.setSha1Mode(value, true)
}

</script>

<template>
    <Dropdown placement="bottom-start">
        <template #button>
            <div
                class="bb"
                :title="collection.groupManager.state.sha1Mode ? 'Image mode' : 'Instance mode'"
            >
                <i :class="collection.groupManager.state.sha1Mode ? 'bi bi-images' : 'bi bi-image'"></i>
        </div>
        </template>
        <template #popup="{ hide }">
            <div class="mode-menu">
                <div
                    class="mode-option"
                    :class="{ selected: !collection.groupManager.state.sha1Mode }"
                    @click="updateSha1Mode(false); hide()"
                >
                    <i class="bi bi-image"></i><span>Instance</span>
                </div>
                <div
                    class="mode-option"
                    :class="{ selected: collection.groupManager.state.sha1Mode }"
                    @click="updateSha1Mode(true); hide()"
                >
                    <i class="bi bi-images"></i><span>Image</span>
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.tool-sm.mode-trigger {
    width: auto;
    gap: 3px;
    padding: 0 5px;
}

.mode-menu {
    padding: 3px;
}

.mode-option {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 10px 4px 8px;
    border-radius: var(--radius-sm);
    cursor: pointer;
    white-space: nowrap;
    color: var(--text-secondary);
}

.mode-option:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.mode-option.selected {
    color: var(--primary);
}
</style>
