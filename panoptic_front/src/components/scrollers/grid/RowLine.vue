<script setup lang="ts">
import CenteredImage from '@/components/images/CenteredImage.vue';
import CheckboxPropInput from '@/components/inputs/CheckboxPropInput.vue';
import ColorPropInput from '@/components/inputs/ColorPropInput.vue';
import DatePropInput from '@/components/inputs/DatePropInput.vue';
import NumberPropInput from '@/components/inputs/NumberPropInput.vue';
import SelectCircle from '@/components/inputs/SelectCircle.vue';
import TagPropInput from '@/components/inputs/TagPropInput.vue';
import TextInput from '@/components/inputs/TextInput.vue';
import TextPropInput from '@/components/inputs/TextPropInput.vue';
import { Image, Property, PropertyType, RowLine, isTag } from '@/data/models';
import { globalStore } from '@/data/store';
import { ImageIterator } from '@/utils/groups';
import { computed, nextTick, onMounted, reactive, ref, unref, watch } from 'vue';
import contenteditable from 'vue-contenteditable';


const props = defineProps({
    item: Object as () => RowLine,
    properties: Array<Property>,
    showImage: Boolean,
    selected: Boolean
    // expandImage: Boolean
})
const emits = defineEmits({
    'resizeHeight': Number,
    'toggle:image': Object,
})

const inputElems = reactive([])
const hover = ref(false)

const tab = computed(() => globalStore.getTab())
const rowHeight = computed(() => {
    let max = 0
    for (let k in sizes) {
        if (sizes[k] > max) {
            max = sizes[k]
        }
    }
    if (props.showImage) {
        return Math.max(max, tab.value.data.imageSize) + 4
    }
    return max + 4
})

const propMinRowHeight = computed(() => {
    const res: { [propId: number]: number } = {}
    for (let prop of props.properties) {
        let max = 0
        for (let k in sizes) {
            if (sizes[k] > max && Number(prop.id) != Number(k)) {
                max = sizes[k]
            }
        }
        if (props.showImage) {
            max = Math.max(max, tab.value.data.imageSize)
        } else {
            max = Math.max(max, 30)
        }
        res[prop.id] = max
    }
    return res
})

const sizes: { [key: string | number]: number } = reactive({})

const propWidth = computed(() => {
    const res = {} as { [propId: number]: number }
    props.properties.forEach(p => res[p.id] == tab.value.data.propertyOptions[p.id].size)
    return res
})

// const totalPropWidth = computed(() => {
//     return Object.values(propWidth.value).reduce((a,b) => a+b, 0)
// })

const classes = computed(() => {
    const res = ['header-cell']
    if (props.item.index == 0) {
        res.push('top-border')
    }
    return res
})


function focusInput(index: number) {
    console.log(inputElems[index])
    inputElems[index].focus()
    // inputElems[index].getInput().focus()
    // inputElems[index].inputElem
}

function log(value: any) {
    console.log(Object.keys(value))
}

let _emitResize = false
function emitResizeOnce() {
    if (_emitResize) return
    _emitResize = true
    nextTick(() => {
        emits('resizeHeight', rowHeight.value)
        _emitResize = false
    })
}

onMounted(emitResizeOnce)
watch(props, emitResizeOnce)
watch(rowHeight, emitResizeOnce)

</script>


<template>
    <div class="container" :style="{ height: props.item.size + 'px' }">
        <div class="left-border" :style="{ height: props.item.size + 'px' }"></div>
        <div v-if="showImage" :class="classes" :style="{
            width: (tab.data.imageSize) + 'px', height: props.item.size + 'px',
        }" class="p-0 m-0" @mouseenter="hover = true" @mouseleave="hover = false">
            <CenteredImage :image="item.data" :width="tab.data.imageSize - 1" :height="tab.data.imageSize - 2"
                :shadow="(props.item.index == 0 && props.item.groupId != '0') ? true : false" />
            <div v-if="hover || props.selected" class="h-100 box-shadow" :style="{width: tab.data.imageSize+'px'}"
                style="position: absolute; top:0; left:0; right: 0; bottom: 0px;"></div>
            <SelectCircle v-if="hover || props.selected" :model-value="props.selected"
                @update:model-value="v => emits('toggle:image', {groupId: item.groupId, imageIndex: item.index})" class="select" :light-mode="true" />
        </div>

        <!-- <div class=""> -->
        <div v-for="property, index in props.properties" :class="classes"
            :style="{ width: (tab.data.propertyOptions[property.id].size) + 'px' }">
            <!-- {{ rowHeight }} -->
            <!-- <template v-if="props.item.data.properties[property.id] != undefined"> -->
            <TextPropInput v-if="property.type == PropertyType.string" :min-height="props.item.size" ref="inputElems"
                @update:height="h => sizes[property.id] = (h)" :image="item.data" :property="property"
                :width="((tab.data.propertyOptions[property.id].size - 7) - (props.properties.length - 1 == index ? 13 : 0))" />
            <TextPropInput v-if="property.type == PropertyType.url" :min-height="props.item.size" :no-nl="true"
                ref="inputElems" @update:height="h => sizes[property.id] = (h)" :image="item.data" :property="property"
                :url-mode="true"
                :width="((tab.data.propertyOptions[property.id].size - 7) - (props.properties.length - 1 == index ? 13 : 0))" />
            <TextPropInput v-if="property.type == PropertyType.path" :min-height="props.item.size" :no-nl="true"
                ref="inputElems" @update:height="h => sizes[property.id] = (h)" :image="item.data" :property="property"
                :url-mode="false"
                :width="((tab.data.propertyOptions[property.id].size - 7) - (props.properties.length - 1 == index ? 13 : 0))" />
            <TagPropInput v-if="isTag(property.type)" :property="property" :image="item.data" ref="inputElems"
                :min-height="propMinRowHeight[property.id]" :input-id="[0, index]"
                @update:height="h => sizes[property.id] = h"
                :max-size="(tab.data.propertyOptions[property.id].size - 5) - (props.properties.length - 1 == index ? 13 : 0)" />
            <CheckboxPropInput v-if="property.type == PropertyType.checkbox" :min-height="propMinRowHeight[property.id]"
                ref="inputElems" @update:height="h => sizes[property.id] = (h)" :image="item.data" :property="property"
                :width="((tab.data.propertyOptions[property.id].size - 7) - (props.properties.length - 1 == index ? 13 : 0))" />
            <ColorPropInput v-if="property.type == PropertyType.color" :min-height="propMinRowHeight[property.id]"
                ref="inputElems" @update:height="h => sizes[property.id] = (h)" :image="item.data" :property="property"
                :width="((tab.data.propertyOptions[property.id].size - 7) - (props.properties.length - 1 == index ? 13 : 0))" />

            <NumberPropInput v-if="property.type == PropertyType.number" :min-height="propMinRowHeight[property.id]"
                ref="inputElems" @update:height="h => sizes[property.id] = (h)" :image="item.data" :property="property"
                :width="((tab.data.propertyOptions[property.id].size - 7) - (props.properties.length - 1 == index ? 13 : 0))" />

            <DatePropInput v-if="property.type == PropertyType.date" :min-height="propMinRowHeight[property.id]"
                ref="inputElems" @update:height="h => sizes[property.id] = (h)" :image="item.data" :property="property"
                :width="((tab.data.propertyOptions[property.id].size - 7) - (props.properties.length - 1 == index ? 13 : 0))" />

            <!-- </template> -->
            <!-- <template v-else>None</template> -->
        </div>
        <!-- </div> -->
    </div>
</template>

<style scoped>
.select {
    position: absolute;
    top: 0;
    left: 5px;
}

.left-border {
    border-left: 1px solid var(--border-color);
    display: inline-block;
    width: 1px;
    /* height: 100%; */
}

.container {
    margin: 0;
    padding: 0;
    display: table;
    table-layout: fixed;
}

.header-cell {
    vertical-align: top;
    border-left: none;
    border-right: 1px solid var(--border-color);
    border-bottom: 1px solid var(--border-color);
    /* overflow: hidden; */
    /* resize: horizontal; */
    padding-top: 3px;
    padding-left: 3px;
    margin: 0;
    display: inline-block;
    /* box-sizing: content-box; */
    /* cursor:text; */
    /* border-top: 1px solid red; */
}

.prop-input {
    margin: 3px;
}

.top-border {
    border-top: none;
}


.box-shadow {
    position: relative;
}

.box-shadow::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    -webkit-box-shadow: inset 0px 24px 25px -20px rgba(0, 0, 0, 0.3);
    -moz-box-shadow: inset 0px 24px 25px -20px rgba(0, 0, 0, 0.3);
    box-shadow: inset 0px 50px 30px -30px rgba(0, 0, 0, 0.5);
    overflow: hidden;
}
</style>