<script setup lang="ts">
import { Colors } from '@/data/models';
import { computed } from 'vue';


const props = withDefaults(defineProps<{
    color?: number
    height?: number
}>(),{
    height: 30
})


const color = computed(() => {
    if (props.color == undefined) return 'white'

    let value = Number(props.color)
    if (isNaN(value) || value > 12 || value < 0) return 'gray'
    return Colors[value].color
})

</script>

<template>
    <div :style="{ height: props.height + 'px', backgroundColor: color }">
    </div>
</template>

<style scoped>
.hidden {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
</style>