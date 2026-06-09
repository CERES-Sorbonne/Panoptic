<script setup lang="ts">
import { computed } from 'vue';
import StampDropdown from '../inputs/StampDropdown.vue';
import wTT from '../tooltips/withToolTip.vue'
import { useProjectStore } from '@/data/projectStore';
import { useDataStore } from '@/data/dataStore';
import ActionButton2 from '../actions/ActionButton2.vue';
import { useTabStore } from '@/data/tabStore';
import WithToolTip from '../tooltips/withToolTip.vue';

const data = useDataStore()

const props = defineProps({
    selectedImagesIds: Array<number>
})

const images = computed(() => props.selectedImagesIds.map(id => data.instances[id]))

const emits = defineEmits(['remove:selected', 'stamped'])

function openSelectionTab() {
    // useTabStore().addTab('Selection', true)
}

</script>

<template>
    <div class="selection-island">
        <WithToolTip message="main.menu.remove_selection_tooltip">
            <div class="seg count-seg" @click="emits('remove:selected')">
                <i class="bi bi-x clear-icon" />
                <span class="count">{{ images.length }}</span>
                <i class="bi bi-image" />
            </div>
        </WithToolTip>
        <div class="seg">
            <WithToolTip message="dropdown.stamp.paint_selection">
                <StampDropdown :images="images" :no-border="true" :show-number="true" @stamped="emits('stamped')" />
            </WithToolTip>
        </div>
        <div class="seg">
            <ActionButton2 action="execute" :images="images" :no-border="true">
                <div class="bi bi-terminal terminal-icon"></div>
            </ActionButton2>
        </div>
    </div>
</template>

<style scoped>
/* PyCharm "New UI" light-island toolbar: a soft, rounded pill with subtle
   segment dividers and gentle hover highlights. */
.selection-island {
    display: flex;
    align-items: center;
    height: var(--bar-tool-height, 28px);
    box-sizing: border-box;
    background-color: var(--surface, #f7f8fa);
    border: 1px solid var(--border-color, #dee2e6);
    border-radius: var(--radius-md, 6px);
    overflow: hidden;
    white-space: nowrap;
    column-gap: 0;
}

.seg {
    display: flex;
    align-items: center;
    height: 100%;
    padding: 0 6px;
    color: var(--text-secondary, #5a6470);
    cursor: pointer;
    border-left: 1px solid var(--border-color, #dee2e6);
    transition: background-color var(--transition-fast, 0.12s ease);
}

.seg:hover {
    background-color: var(--hover-bg, rgba(137, 176, 205, 0.18));
    color: var(--text-primary, #1f2328);
}

.count-seg {
    gap: 3px;
    font-size: var(--font-size-sm, 0.8rem);
    /* first segment — no leading divider */
    border-left: none;
}

.count {
    font-weight: var(--font-weight-bold, 600);
    color: var(--text-primary, #1f2328);
}

.clear-icon {
    font-size: 16px;
    line-height: 1;
    margin-right: -2px;
}

.terminal-icon {
    font-size: 14px;
    line-height: 1;
}
</style>