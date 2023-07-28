<script setup lang="ts">
import { Property } from '@/data/models';
import { globalStore } from '@/data/store';
import { computed, onMounted, reactive, ref, unref } from 'vue';
import { useResizeObserver } from '@vueuse/core'
import Resizable from '@/components/Resizable.vue';
import PropertyIcon from '@/components/properties/PropertyIcon.vue';

const props = defineProps({
    properties: Array<Property>,
    showImage: Boolean
})

const hearderHeight = ref(30)
const tab = computed(() => globalStore.getTab())

const elems = reactive({})

function resize(propId, w) {
    tab.value.data.propertyOptions[propId].size = w
}
</script>


<template>
    <div style="height: 30px;">
        <div class="left-border" ></div>
        <div v-if="showImage" class="header-cell" :style="{ width: tab.data.imageSize+'px' }"><i class="bi bi-image ms-1 me-1"></i> Image</div>
        <Resizable :start-width="tab.data.propertyOptions[property.id].size" v-for="property in props.properties" class="header-cell" @resize="w => resize(property.id, w)" >
            <PropertyIcon :type="property.type" class="ms-1"/>
            {{ property.name }}
        </Resizable>
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

</style>