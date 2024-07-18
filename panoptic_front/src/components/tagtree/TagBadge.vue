<script setup lang="ts">
import { useDataStore } from '@/data/dataStore';
import { Colors, ModalId } from '@/data/models';
import { usePanopticStore } from '@/data/panopticStore';
import { computed } from 'vue';

const data = useDataStore()

const props = defineProps<{
  showDelete?: boolean,
  id?: number,
  name?: string,
  color?: number
}>()

const tag = computed(() => data.tags[props.id])

const color = computed(() => {
  if (props.color >= 0 && props.color <= 12) return Colors[props.color].color
  if (!tag.value) return 'grey'
  if (tag.value.color < 0 || tag.value.color > 12) return 'grey'
  return Colors[tag.value.color].color
})

const name = computed(() => {
  if (props.name) return props.name
  if (!tag.value) return 'undefined'
  return tag.value.value
})

function click() {
  if (!tag.value) return
  const panoptic = usePanopticStore()
  panoptic.showModal(ModalId.TAG, { propId: tag.value.propertyId, tagId: tag.value.id })
}

</script>


<template>
  <div class="badge tag-badge" :style="'background: ' + color" @dblclick="click">
    <span class="m-0 p-0">
      <span v-if="showDelete" @click.prevent.stop="$emit('delete')" class="bi bi-x tag-x"></span>
      {{ name }}
    </span>
  </div>
</template>


<style scoped>
.tag-badge {
  position: relative;
  top: -1px;
  margin: 0;
  padding: 3px 3px;
  border-radius: 5px !important;
  /* background: rgb(169, 169, 255); */
}

.tag-x:hover {
  cursor: pointer;
}
</style>