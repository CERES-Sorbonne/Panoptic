<script setup lang="ts">
import { computed, onMounted, reactive, ref, unref } from 'vue';
import { useResizeObserver } from '@vueuse/core'
import Resizable from '@/components/Resizable.vue';
import PropertyIcon from '@/components/properties/PropertyIcon.vue';
import PropertyValue from '@/components/properties/PropertyValue.vue';
import { Property } from '@/data/models';
import { Group, GroupManager } from '@/core/GroupManager';
import { getGroupParents } from '@/utils/utils';
import PropertyOptions from '@/components/menu/PropertyOptions.vue';
import { useProjectStore } from '@/data/projectStore';

const project = useProjectStore()

const props = defineProps({
    properties: Array<Property>,
    missingWidth: Number,
    showImage: Boolean,
    manager: GroupManager,
    currentGroup: Object as () => Group
})

const hearderHeight = ref(30)
const tab = computed(() => project.getTab())

const elems = reactive({})

const totalPropertyWidth = computed(() => {
    return props.properties.map(p => tab.value.propertyOptions[p.id].size).reduce((a, b) => a + b, 0) + tab.value.imageSize
})

const isMissingWidth = computed(() => props.missingWidth > 0)

function resize(propId, w) {
    tab.value.propertyOptions[propId].size = w
}

const propertyValues = computed(() => {
    const res = []
    if (props.currentGroup.id != undefined) {
        props.currentGroup.meta.propertyValues
        const parents = getGroupParents(props.currentGroup)
        parents.forEach(p => res.push(...p.meta.propertyValues))
    }

    return res
})

</script>


<template>
    <div class="m-0 p-0">
        <div class="header-row d-flex flex-row ps-1">
            <span v-if="props.manager.hasResult()" class=" me-1">Images: {{ props.manager.result.root.images.length
            }}</span>
            <span v-if="props.currentGroup.id != undefined"> ({{ props.currentGroup.images.length }})</span>
            <div class="ms-3 me-1"></div>
            <template v-if="props.currentGroup.id">
                <template v-for="value, index in propertyValues">
                    <PropertyValue class="" :value="value" />
                    <div v-if="index < propertyValues.length - 1" class="separator">&</div>
                </template>
            </template>
        </div>
        <div class="empty"></div>

        <div style="height: 30px;">
            <div class="left-border"></div>
            <div v-if="showImage" class="header-cell right-border" :style="{ width: (tab.imageSize) + 'px' }">
                <i class="bi bi-image ms-1 me-1"></i>
            </div>
            <Resizable
                :start-width="tab.propertyOptions[property.id].size - ((isMissingWidth && index == props.properties.length - 1) ? 1 : 0)"
                v-for="property, index in props.properties" class="header-cell"
                :class="(isMissingWidth && index == props.properties.length - 1) ? '' : 'right-border'"
                @resize="w => resize(property.id, w)">
                <PropertyIcon :type="property.type" class="ms-1" />
                {{ property.name }}
            </Resizable>
            <div v-if="isMissingWidth" class="header-cell right-border"
                :style="{ width: (props.missingWidth) + 'px', height: '30px' }"></div>
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

.no-right-border {
    border-right: 1px solid rgba(255, 255, 255, 0);
}

.right-border {
    border-right: 1px solid var(--border-color);
}


.header-cell {
    border-left: none;
    border-top: 1px solid var(--border-color);
    /* border-right: 1px solid var(--border-color); */
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