<script setup lang="ts">
import { CollectionManager } from '@/core/CollectionManager';
import { Group, GroupIterator } from '@/core/GroupManager';
import { useDataStore } from '@/data/dataStore';
import { PropertyType } from '@/data/models';
import { ref } from 'vue'
import LineChart from './LineChart.vue'

const dataStore = useDataStore()
const props = defineProps<{
    collection: CollectionManager
    height: number
}>()
const emits = defineEmits([])
const error = ref("")

const chartData = ref(computeSeries())

function getAllPropValues() {
    const allPropValues = new Set();
    let it: GroupIterator = props.collection.groupManager.getGroupIterator()
    while (it) {
        const group = it.group
        // on est root
        if (group.id === 0 || (group.meta.propertyValues && group.meta.propertyValues[0].value == undefined)) {
            it = it.nextGroup()
            continue
        }
        // on est une date, on parcourt tous les enfants
        for (let child of group.children) {
            allPropValues.add(child.meta.propertyValues[0].value)
        }
        group.children.forEach(() => it = it.nextGroup())
        it = it.nextGroup()
    }
    return allPropValues;
}

function computeSeries() {
    const res: { [key: string | number]: { [key: string]: any } } = {}
    let allPropValues;
    let properties = props.collection.groupManager.state.groupBy

    if (properties.length === 0) {
        error.value = "Choose at least one date or numeric value to group the images by"
        return
    }
    const firstProp = dataStore.properties[properties[0]]
    const firstPropType = firstProp.type

    if (properties.length > 2) {
        error.value = "Only max two levels of grouping are supported"
        return
    }
    else if (properties.length === 1) {
        res[firstProp.name] = { name: firstProp.name, data: [] }
    }
    else {
        // pre-compute all prop values to fill empty groups with 0 
        allPropValues = Array.from(getAllPropValues())
        if(allPropValues.length > 20){
            error.value = "Too many curves to draw, select a subgrouping with less than 20 possible values"
            return
        }
    }
    if (firstPropType !== PropertyType.number && firstPropType !== PropertyType.date) {
        error.value = "First level of grouping needs to be a date or a numeric property"
        return
    }
    let it: GroupIterator = props.collection.groupManager.getGroupIterator()
    const xValues = []
    while (it) {
        const group: Group = it.group
        if (group.id === 0 || (group.meta.propertyValues && group.meta.propertyValues[0].value == undefined)) {
            it = it.nextGroup()
            continue
        }
        let propValue = group.meta.propertyValues[0]
        // convert date to a Date object if prop is a date
        const xValue = firstPropType === PropertyType.date ? new Date(propValue.value).getTime() : propValue.value
        xValues.push(xValue)
        if (firstProp.name in res) {
            res[firstProp.name].data.push({ x: xValue, y: group.images.length, images: group.images.slice(0, 20).map(i => i.urlSmall) })
        }
        else {
            const childValues = group.children.map(el => el.meta.propertyValues[0].value)
            const missingValues = allPropValues.filter(el => !childValues.includes(el))
            for (let child of group.children) {
                const childValue = child.meta.propertyValues[0].value
                if (res[childValue] === undefined) {
                    let value = childValue
                    // check if it's a tag or not
                    if (childValue in dataStore.tags) {
                        value = dataStore.tags[childValue].value
                    }
                    res[childValue] = { data: [], name: value }
                }
                res[child.meta.propertyValues[0].value].data.push({ x: xValue, y: child.images.length, images: child.images.slice(0, 20).map(i => i.urlSmall) })
            }
            // console.log(xValue, missingValues)
            for (let missing of missingValues) {
                if (res[missing] === undefined) {
                    let value = missing
                    // check if it's a tag or not
                    if (missing in dataStore.tags) {
                        value = dataStore.tags[missing].value
                    }
                    res[missing] = { data: [], name: value }
                }
                res[missing].data.push({ x: xValue, y: 0, images: [] })
            }
            group.children.forEach(() => it = it.nextGroup())
        }
        it = it.nextGroup()
    }

    error.value = ""
    return {
        series: Object.values(res),
        xValues: xValues,
        dataType: firstPropType
    }
}
props.collection.groupManager.onResultChange.addListener(() => chartData.value = computeSeries())
</script>

<template>
    <div class="" :style="{ height: props.height + 'px' }">
        <line-chart :chartData="chartData" :height="(props.height - 50) + 'px'" v-if="error === ''" />
        <span v-else>{{ error }}</span>
    </div>
</template>

<style scoped></style>