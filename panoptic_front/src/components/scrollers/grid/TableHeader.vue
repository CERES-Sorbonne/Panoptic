<script setup lang="ts">
import { computed } from 'vue';
import Resizable from '@/components/Resizable.vue';
import PropertyIcon from '@/components/properties/PropertyIcon.vue';
import PropertyValue from '@/components/properties/PropertyValue.vue';
import { Property } from '@/data/models';
import { Group} from '@/core/GroupManager'
import type { GroupInspector } from '@/core/group/inspector'
import { getGroupParents } from '@/utils/utils';
import { useProjectStore } from '@/data/projectStore';
import { TabManager } from '@/core/TabManager';

const project = useProjectStore()

const props = defineProps<{
    tab: TabManager
    imageSize: number,
    properties: Property[],
    missingWidth: number,
    showImage: boolean,
    manager: GroupInspector,
    currentGroup: Group
}>()

const tab = computed(() => props.tab.state)
// Depends on the version tick so it re-evaluates whenever the result tree changes
// (the result itself is not reactive).
const instanceNb = computed(() => {
    props.manager.version.value
    if (!props.manager.hasResult()) return undefined
    return props.manager.result.root?.slots.length ?? 0
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
    <div class="m-0">
        <div style="height: 30px;">
            <!-- <div class="left-border"></div> -->
            <div v-if="showImage" class="header-cell right-border" :style="{ width: (props.imageSize) + 'px' }">
                <i class="bi bi-image me-1" style="margin-left: 0.35rem;"></i>
                <span v-if="instanceNb != undefined">{{ instanceNb }}</span>
            </div>
            <Resizable :start-width="tab.propertyOptions[property.id].size"
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