<script setup lang="ts">
import { useProjectStore } from '@/data/projectStore';
import { defineProps, defineEmits, ref, computed } from 'vue'
import { getTabManager } from '@/utils/utils';

const project = useProjectStore()

// const props = defineProps<{}>()
const emits = defineEmits([])

const mode = computed(() => {
    if(project.getTab().autoReload) {
        return 2
    }
    if(getTabManager().collection.state.isDirty) {
        return 0
    }
    return 1
})

function toggleMode() {
    if(mode.value == 0) {
        getTabManager().collection.update()
    }
    else if(mode.value == 1) {
        project.getTab().autoReload = true
        project.updateTabs()
    }
    else {
        project.getTab().autoReload = false
        project.updateTabs()
    }
}

</script>

<template>
    <div class="bb font" @click="toggleMode" style="width: 26px; height: 30px; overflow: hidde;">
        <span v-if="mode == 0" class="bi bi-arrow-repeat text-warning"></span>
        <span v-if="mode == 1" class="bi bi-check2-all text-success"></span>
        <span v-if="mode == 2">
            <span class="bi bi-check2-all text-success small-valid"></span>
            <span class="bi bi-arrow-repeat big-arrow text-warning" style="opacity: 0.3;"></span>
        </span>
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
    top: -8px;
    left: -1px;
    transform: rotate(90deg);
    display: block;
}

</style>