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
    <div class="d-flex b-border">
        <WithToolTip message="main.menu.remove_selection_tooltip">
            <div class="sb no-radius m-0" style="padding: 0px 4px 0 0;" @click="emits('remove:selected')"><i
                    class="bi bi-x" />{{ images.length }} <i class="bi bi-image" /> </div>
        </WithToolTip>
        <div class="no-radius left-border">
            <WithToolTip message="dropdown.stamp.paint_selection">
            <StampDropdown :images="images" :no-border="true" :show-number="true" @stamped="emits('stamped')" />
            </WithToolTip>
        </div>
        <div class="no-radius left-border">
            <ActionButton2 action="execute" :images="images" :no-border="true">
                <div class="sb bi bi-terminal" style="position: relative; font-size: 14px; padding: 0px 3px;"></div>
            </ActionButton2>
        </div>
        <!-- <div class="no-radius left-border" @click="openSelectionTab">
            <div class="sb bi bi-bookmark-plus" style="position: relative; font-size: 14px; padding: 0px 3px;"></div>
        </div> -->
    </div>
</template>

<style scoped>
.b-border {
    border: 1px solid var(--blue);
    overflow: hidden;
    white-space: nowrap;
    border-radius: 3px;
    align-items: center;
    column-gap: 0px;
    /* padding: 1px 1px; */
}

.no-radius {
    border-radius: 0;
}

.left-border {
    border-left: 1px solid var(--blue);
}
</style>