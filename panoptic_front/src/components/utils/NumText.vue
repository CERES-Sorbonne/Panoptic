<script setup lang="ts">
// A translated sentence with number placeholders, e.g. "{count} images".
// Each value is shown in the number font (.num); the words around it keep the body font.
defineProps<{
    keypath: string
    values: Record<string, string | number>
}>()
</script>

<template>
    <i18n-t :keypath="keypath" scope="global">
        <template v-for="(value, name) in values" :key="name" #[name]><span class="num">{{ value }}</span></template>
    </i18n-t>
</template>
