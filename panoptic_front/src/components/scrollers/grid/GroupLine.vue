<script setup lang="ts">
import PropertyValueVue from '@/components/properties/PropertyValue.vue';
import { PropertyValue, ScrollerLine }from '@/data/models';


const props = defineProps({
    item: Object as () => ScrollerLine,
    propValues: Array<PropertyValue>,
    width: Number
})

</script>

<template>
    <div class="d-flex flex-row group-row m-0" :style="{width: (props.width-2)+'px', height: props.item.size+'px'}">
        <template v-for="value, index in props.propValues">
            <PropertyValueVue class="" :value="value" />
            <div v-if="index < props.propValues.length - 1" class="separator"></div>
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
    line-height: 30px;
}

.separator {
    border-left: 2px solid var(--border-color);
    margin: 3px 4px;
}

</style>