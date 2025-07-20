<script setup lang="ts">
</script>

<template>
    <div class="d-flex">
        <div><slot /></div>
        <div class="hr ms-2 flex-grow-1 align-self-center"></div>
    </div>
</template>

<style scoped>
.hr {
    border-bottom: 1px solid var(--border-color, #ccc);
    height: 0;
}
</style>
