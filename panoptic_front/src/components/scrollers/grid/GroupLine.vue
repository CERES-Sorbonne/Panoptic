<script setup lang="ts">
import SelectCircle from '@/components/inputs/SelectCircle.vue';
import PropertyValueVue from '@/components/properties/PropertyValue.vue';
import { GroupLine, PropertyValue, ScrollerLine } from '@/data/models';
import { getGroupParents } from '@/utils/utils';
import { computed, guardReactiveProps } from 'vue';


const props = defineProps({
    item: Object as () => GroupLine,
    width: Number
})
const emits = defineEmits(['close:group', 'open:group', 'toggle:group'])

const closed = computed(() => getGroupParents(props.item.data).some(g => g.view.closed) || props.item.data.view.closed)

function toggleClosed() {
    if (closed.value) {
        emits('open:group', props.item.data.id)
    }
    else {
        emits('close:group', props.item.data.id)
    }
}

const propertyValues = computed(() => {
    const res = []
    if (props.item.data.id != undefined) {
        res.push(...props.item.data.meta.propertyValues)
        const parents = getGroupParents(props.item.data)
        parents.forEach(p => res.push(...p.meta.propertyValues))
    }
    return res
})

</script>

<template>
    <div class="d-flex flex-row group-row m-0"
        :style="{ width: (props.width - 0) + 'px', height: (props.item.size) + 'px' }">
        <div @click="toggleClosed" class="align-self-center me-2" style="cursor: pointer;">
            <i v-if="closed" class="bi bi-caret-right-fill" style="margin-left: 1px;"></i>
            <i v-else class="bi bi-caret-down-fill" style="margin-left: 1px;"></i>
        </div>
        <div class="me-2"><SelectCircle :model-value="props.item.data.view.selected" @update:model-value="emits('toggle:group', props.item.data.id)"/></div>
        <template v-for="value, index in propertyValues">
            <PropertyValueVue class="" :value="value" />
            <div v-if="index < propertyValues.length - 1" class="separator">&</div>
        </template>
    </div>
</template>

<style scoped>
.group-row {
    border-left: 1px solid var(--border-color);
    border-right: 1px solid var(--border-color);
    border-bottom: 1px solid var(--border-color);
    box-sizing: border-box;
    background-color: rgb(249, 249, 249);
    padding-top: 2px;
    padding-left: 2px;
    line-height: 28px;
    position: relative;
    /* box-shadow: 0px 2px 3px var(--border-color); */
    /* z-index: 5; */
}

.separator {
    /* border-left: 2px solid var(--border-color); */
    margin: 0px 10px;
    color: gray;
}
</style>