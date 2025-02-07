<script setup lang="ts">
import { computed } from 'vue'
import wTT from '@/components/tooltips/withToolTip.vue'
import { TabManager } from '@/core/TabManager';

const props = defineProps<{
    tab: TabManager
}>()
const emits = defineEmits([])

const mode = computed(() => {
    if (props.tab.collection.state.autoReload) {
        return 2
    }
    if (props.tab.collection.runState.isDirty) {
        return 0
    }
    return 1
})

function toggleMode() {
    if (mode.value == 0) {
        props.tab.collection.update()
    }
    else if (mode.value == 1) {
        props.tab.collection.setAutoReload(true)
    }
    else {
        props.tab.collection.setAutoReload(false)
    }
}

</script>

<template>
    <div class="bb font" @click="toggleMode" style="width: 26px; height: 30px; overflow: hidde;">
        <wTT v-if="mode == 0" message="btn.reload.dirty" pos="bottom">
            <span class="bi bi-arrow-repeat text-warning"></span>
        </wTT>
        <wTT v-if="mode == 1" message="btn.reload.valid" pos="bottom">
            <span class="bi bi-check2-all text-success"></span>
        </wTT>
        <wTT v-if="mode == 2" message="btn.reload.auto" pos="bottom">
            <div style="height: 30px;">
                <span class="bi bi-check2-all text-success small-valid"></span>
                <span class="bi bi-arrow-repeat big-arrow text-warning" style="opacity: 0.3;"></span>
            </div>
        </wTT>
    </div>
</template>

<style scoped>
.font {
    font-size: 20px !important;
}

.small-valid {
    position: absolute;
    top: 3px;
    left: 4px;
    font-size: 18px !important;
}

.big-arrow {
    position: relative;
    font-size: 26px !important;
    top: -5px;
    left: -4px;
    transform: rotate(90deg);
    display: block;
}
</style>