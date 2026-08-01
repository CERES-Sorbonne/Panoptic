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

// data.instances only holds instances registered by a visible component, while a selection
// can span instances that were never rendered. Fall back to a minimal stub so consumers
// (stamping, actions) still get every selected id.
const images = computed(() => (props.selectedImagesIds ?? []).map(id => data.instances[id] ?? ({ id } as any)))

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
    /* Same selection ring as a selected image cell (.img-border.selected::after) */
    border: 2px solid var(--primary, #4f46e5);
    border-radius: var(--radius-md, 6px);
    overflow: hidden;
    white-space: nowrap;
    column-gap: 0;
}

/* The first segment is wrapped in a tooltip trigger, which is inline-flex and centers its
   child — leaving the segment shorter than the island and offset from the top border. */
.selection-island > :deep(.wtt-trigger) {
    height: 100%;
    align-items: stretch;
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

/* The buttons inside a segment carry their own small hover rectangle (.sb, .main2, …),
   which highlights less than the segment it sits in and reads as a dead gap next to the
   border. Let the segment own the hover: stretch every wrapper to fill it and drop the
   inner highlights. */
.seg :deep(> *),
.seg :deep(.wtt-trigger),
.seg :deep(.main2),
.seg :deep(.slot-wrap),
.seg :deep(.slot-inner) {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    flex: 1;
}

.seg :deep(.sb),
.seg :deep(.sbb) {
    border: none;
    top: 0;
    border-radius: 0;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
}

.seg :deep(.sb:hover),
.seg :deep(.sbb:hover) {
    background-color: transparent !important;
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