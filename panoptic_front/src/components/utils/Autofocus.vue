<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'

const elem = ref(null)

onMounted(async () => {
    await nextTick()
    elem.value.focus()
})
</script>

<template>
    <div ref="elem" tabindex="1">
        <slot>

        </slot>
    </div>
</template>

<style scoped></style>