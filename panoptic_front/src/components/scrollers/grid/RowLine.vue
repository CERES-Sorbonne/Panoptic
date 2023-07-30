<script setup lang="ts">
import ImageVue from '@/components/images/Image.vue';
import CheckboxPropInput from '@/components/inputs/CheckboxPropInput.vue';
import DatePropInput from '@/components/inputs/DatePropInput.vue';
import NumberPropInput from '@/components/inputs/NumberPropInput.vue';
import TagPropInput from '@/components/inputs/TagPropInput.vue';
import TextInput from '@/components/inputs/TextInput.vue';
import TextPropInput from '@/components/inputs/TextPropInput.vue';
import { Image, Property, PropertyType, RowLine, isTag } from '@/data/models';
import { globalStore } from '@/data/store';
import { computed, nextTick, onMounted, reactive, ref, unref, watch } from 'vue';
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

const inputElems = reactive([])

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
    return Math.max(max, 30)
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
    if(_emitResize) return
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
        <div class="left-border"></div>
        <div v-if="showImage" :class="classes" :style="{
            width: (tab.data.imageSize) + 'px',
        }" class="p-0 m-0">
            <ImageVue :image="item.data" :constraint-width="true" :size="tab.data.imageSize - 2" :hide-properties="true"
                :no-border="true" />
        </div>
        <!-- <div class=""> -->
        <div v-for="property, index in props.properties" :class="classes"
            :style="{ width: (tab.data.propertyOptions[property.id].size) + 'px' }">
            <!-- {{ rowHeight }} -->
            <!-- <template v-if="props.item.data.properties[property.id] != undefined"> -->
            <TextPropInput v-if="property.type == PropertyType.string" :min-height="propMinRowHeight[property.id]"
                ref="inputElems" @update:height="h => sizes[property.id] = (h)" :image="item.data" :property="property"
                :width="((tab.data.propertyOptions[property.id].size - 7) - (props.properties.length - 1 == index ? 13 : 0))" />
            <TextPropInput v-if="property.type == PropertyType.url" :min-height="propMinRowHeight[property.id]"
                :no-nl="true" ref="inputElems" @update:height="h => sizes[property.id] = (h)" :image="item.data"
                :property="property" :url-mode="true"
                :width="((tab.data.propertyOptions[property.id].size - 7) - (props.properties.length - 1 == index ? 13 : 0))" />
            <TextPropInput v-if="property.type == PropertyType.path" :min-height="propMinRowHeight[property.id]"
                :no-nl="true" ref="inputElems" @update:height="h => sizes[property.id] = (h)" :image="item.data"
                :property="property" :url-mode="false"
                :width="((tab.data.propertyOptions[property.id].size - 7) - (props.properties.length - 1 == index ? 13 : 0))" />
            <TagPropInput v-if="isTag(property.type)" :property="property" :image="item.data" ref="inputElems"
                :min-height="propMinRowHeight[property.id]" :input-id="[0, index]"
                @update:height="h => sizes[property.id] = h"
                :max-size="(tab.data.propertyOptions[property.id].size - 5) - (props.properties.length - 1 == index ? 13 : 0)" />
            <CheckboxPropInput v-if="property.type == PropertyType.checkbox" :min-height="propMinRowHeight[property.id]"
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
.left-border {
    border-left: 1px solid var(--border-color);
    display: inline-block;
    width: 1px;
    height: 100%;
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
    /* overflow: scroll; */
    /* resize: horizontal; */
    padding-top: 3px;
    padding-left: 3px;
    margin: 0;
    display: table-cell;
    /* height: 100%; */
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
</style>