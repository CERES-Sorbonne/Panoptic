<script setup lang="ts">
import { computed } from 'vue';
import { formatDate } from './formatDate';


const props = withDefaults(defineProps<{
    date?: string
    format?: string
    resolution?: number
}>(), {
    format: "YMDhms",
    resolution: 5
})

const dateString = computed(() => formatDate(props.date, props.format))

</script>

<template>
    <div>
        <span v-if="!dateString" class="text-secondary">{{ $t('none') }}</span>
        <span v-else>{{ dateString }}</span>
    </div>
</template>

<style scoped></style>