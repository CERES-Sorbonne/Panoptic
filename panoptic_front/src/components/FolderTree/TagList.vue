<script setup lang="ts">
import { TreeTag } from '@/data/models';
import TagNode from './TagNode.vue';


const props = defineProps({
    tags: Array<TreeTag>,
    root: {type: Boolean, default: true}
})

</script>

<template>
    <ul :class="props.root ? 'tree' : ''" :style="props.root ? 'padding-left:0px;' : ''">
        <li v-for="tag in props.tags" :style="props.root ? 'padding-left:0px;' : ''">
            <TagNode :node="tag"/>
        </li>
    </ul>
</template>

<style scoped>

.tree ul {
  margin-left: calc(var(--radius) - var(--spacing));
  /* margin-left: 0; */
  padding-left: 10px !important;
  margin-bottom: 0;
}

</style>