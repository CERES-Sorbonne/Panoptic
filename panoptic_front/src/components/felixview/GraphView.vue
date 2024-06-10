<script setup lang="ts">
import { CollectionManager } from '@/core/CollectionManager';
import { Group, GroupIterator, GroupManager } from '@/core/GroupManager';
import { useDataStore } from '@/data/dataStore';
import { PropertyType } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import { defineProps, defineEmits, computed, ref } from 'vue'
import LineChart from './LineChart.vue'

const dataStore = useDataStore()
const props = defineProps<{
  collection: CollectionManager
  height: number
}>()
const emits = defineEmits([])
const error = ref("")

const series = ref(computeSeries())

function computeSeries(){
  const res:{[key: string | number]: {[key: string] : any}} = {}

  let properties = props.collection.groupManager.state.groupBy
  if( properties.length > 2){
      error.value = "Only max two levels of grouping are supported"
      return
  }
  else if (properties.length === 1){
    res['date'] = {name: 'date', data: []}
  }
  let it: GroupIterator = props.collection.groupManager.getGroupIterator()
  while (it) {
    const dates = []
    const group: Group = it.group
    if (group.id === "root") {
      it = it.nextGroup()
      continue
    }
    let propValue = group.meta.propertyValues[0]

    if ('date' in res){
      if(propValue.unit === undefined){
        error.value = "First level of grouping needs to be a date property"
        return
      }
      const date = propValue.value.getTime()
      res['date'].data.push({x: date, y:group.images.length, images: group.images.slice(0, 10).map(i => i.url)})
    }
    else{
      const date = propValue.value.getTime()
      // const childValues = group.children.map(el => el.meta.propertyValues[0].value)
      // const missingValues = allPropValues.filter(el => !childValues.includes(el))
      for(let child of group.children){
        const childValue = child.meta.propertyValues[0].value
        if(res[childValue] === undefined){
          let value = childValue
          // check if it's a tag or not
          if(childValue in dataStore.tags){
            value = dataStore.tags[childValue].value
          }
          res[childValue] = {data: [], name: value}
        }
        res[child.meta.propertyValues[0].value].data.push({x: date, y: child.images.length, images: child.images.slice(0, 10).map(i => i.url)})
      }
      // for(let missing of missingValues){
      //   res[missing].data.push([date, 0])
      // }
      group.children.forEach(() => it = it.nextGroup())
    }
    it = it.nextGroup()
  }
  error.value = ""
  console.log(res)
  return Object.values(res)
}
props.collection.groupManager.onChange.addListener(() => series.value = computeSeries())
</script>

<template>
  <div class="" :style="{ height: props.height + 'px' }">
    <!-- <div>{{ props.collection.filterManager.state }}</div>
    <div>{{ props.collection.sortManager.state }}</div>
    <div>{{ props.collection.groupManager.state }}</div>
    <span v-for="item in data">{{item}}</span> -->
    <line-chart :series="series" :height="(props.height - 50) + 'px'" v-if="error === ''"/>
    <span v-else>{{error}}</span>
  </div>
</template>

<style scoped></style>