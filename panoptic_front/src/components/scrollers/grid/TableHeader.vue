<script setup lang="ts">
import { Group, GroupData, Property } from '@/data/models';
import { globalStore } from '@/data/store';
import { computed, onMounted, reactive, ref, unref } from 'vue';
import { useResizeObserver } from '@vueuse/core'
import Resizable from '@/components/Resizable.vue';
import PropertyIcon from '@/components/properties/PropertyIcon.vue';
import PropertyValue from '@/components/properties/PropertyValue.vue';

const props = defineProps({
    properties: Array<Property>,
    showImage: Boolean,
    data: Object as () => GroupData,
    currentGroup: Object as () => Group
})

const hearderHeight = ref(30)
const tab = computed(() => globalStore.getTab())

const elems = reactive({})

function resize(propId, w) {
    tab.value.data.propertyOptions[propId].size = w
}
</script>


<template>
    <div class="m-0 p-0">
        <div class="header-row d-flex flex-row ps-1">
            <span v-if="props.data.root" class=" me-1">Images: {{ props.data.root.count }}</span>
            <span v-if="props.currentGroup"> ({{ props.currentGroup.count }})</span>
            <div class="ms-3 me-1"></div>
            <template v-if="props.currentGroup.id">
                <template v-for="value, index in currentGroup.propertyValues">
                    <PropertyValue class="" :value="value" />
                    <div v-if="index < currentGroup.propertyValues.length - 1" class="separator">&</div>
                </template>
            </template>
        </div>
        <div class="empty"></div>

        <div style="height: 30px;">
            <div class="left-border"></div>
            <div v-if="showImage" class="header-cell" :style="{ width: (tab.data.imageSize) + 'px' }">
                <i class="bi bi-image ms-1 me-1"></i>
            </div>
            <Resizable :start-width="tab.data.propertyOptions[property.id].size" v-for="property in props.properties"
                class="header-cell" @resize="w => resize(property.id, w)">
                <PropertyIcon :type="property.type" class="ms-1" />
                {{ property.name }}
            </Resizable>
        </div>
        
    </div>
</template>

<style scoped>
.left-border {
    border-left: 1px solid var(--border-color);
    display: inline-block;
    width: 1px;
    height: 30px;
}

.header-cell {
    border-left: none;
    border-top: 1px solid var(--border-color);
    border-right: 1px solid var(--border-color);
    border-bottom: 1px solid var(--border-color);
    overflow: hidden;
    /* resize: horizontal; */
    padding: 2px;
    display: inline-block;
    margin: 0;
}

.header-row {
    /* border: 1px solid var(--border-color);
    border-bottom: none; */
    height: 30px;
    /* line-height: 30px; */
}

.separator {
    /* border-left: 2px solid var(--border-color); */
    margin: 0 16px;
    color: gray
}

.empty {
    height: 0px;
    /* border-top: 1px solid var(--border-color); */
}
</style>