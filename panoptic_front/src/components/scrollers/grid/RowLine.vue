<script setup lang="ts">
import ImageVue from '@/components/images/Image.vue';
import TextInput from '@/components/inputs/TextInput.vue';
import { Image, Property, RowLine } from '@/data/models';
import { globalStore } from '@/data/store';
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import contenteditable from 'vue-contenteditable';


const props = defineProps({
    item: Object as () => RowLine,
    properties: Array<Property>,
    showImage: Boolean,
    // expandImage: Boolean
})
const emits = defineEmits({
    'resizeHeight': Number
})

const tab = computed(() => globalStore.getTab())
const rowHeight = computed(() => {
    let max = 0
    for(let k in sizes) {
        if(sizes[k] > max) {
            max = sizes[k]
        }
    }
    if(props.showImage) {
        return Math.max(max, tab.value.data.imageSize)
    }
    return Math.max(max, 30)
})

const sizes: {[key: string|number]:number} = reactive({})

const classes = computed(() => {
    const res = ['header-cell']
    if(props.item.index == 0) {
        res.push('top-border')
    }
    return res
})


function resizeImage(size: {width:number, height:number}) {
}

onMounted(() => emits('resizeHeight', rowHeight.value))
watch(props, () => emits('resizeHeight', rowHeight.value))
watch(rowHeight, () => emits('resizeHeight', rowHeight.value))

</script>


<template>
    <div class="container" :style="{height: props.item.size+'px'}">
        <div class="left-border" ></div>
        <div v-if="showImage" :class="classes" :style="{ width: tab.data.imageSize+'px' }" class="p-0 m-0">
            <ImageVue :image="item.data" :constraint-width="false" :size="tab.data.imageSize" :hide-properties="true" @resize="resizeImage" :no-border="true"/>
        </div>
        <div v-for="property in props.properties" :class="classes" :style="{ width:  tab.data.propertyOptions[property.id].size+'px'}">
            <div v-if="props.item.data.properties[property.id] != undefined">
                <TextInput @update:height="h => sizes[property.id] = h" v-model="props.item.data.properties[property.id].value" tag="div" :no-html="true" :width="tab.data.propertyOptions[property.id].size-4"/>
            </div>
            <div v-else>None</div>
        </div>
    </div>
</template>

<style scoped>

.left-border {
    border-left: 1px solid var(--border-color);
    display: inline-block;
    width: 1px;
    height: 100%;
}

.container {
    margin: 0;
    padding: 0;
}

.header-cell {
    border-left: none;
    border-right: 1px solid var(--border-color);
    border-bottom: 1px solid var(--border-color);
    overflow: hidden;
    /* resize: horizontal; */
    padding: 2px;
    display: inline-block;
    height: 100%;
}
.top-border {
    border-top: none;
}


</style>