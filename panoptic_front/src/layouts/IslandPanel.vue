<script setup lang="ts">
// A single white "island" card: rounded, bordered, soft-shadowed surface with
// an optional header and a body. Pure layout — slots only.
interface Props {
    width?: number
    height?: number
    grow?: boolean
}

withDefaults(defineProps<Props>(), {
    grow: false
})
</script>

<template>
    <div
        class="island"
        :class="{ grow }"
        :style="{
            width: width ? width + 'px' : undefined,
            height: height ? height + 'px' : undefined
        }"
    >
        <div v-if="$slots.header" class="island-header">
            <slot name="header"></slot>
        </div>
        <div class="island-body">
            <slot></slot>
        </div>
    </div>
</template>

<style scoped>
.island {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-sizing: border-box;
    background-color: var(--island-surface);
    border: 1px solid var(--island-border);
    border-radius: var(--island-radius);
    box-shadow: var(--island-shadow);
}

.island.grow {
    flex: 1;
    min-width: 0;
    min-height: 0;
}

/* Fixed-size islands keep their size in a flex stack */
.island:not(.grow) {
    flex-shrink: 0;
}

.island-header {
    flex-shrink: 0;
}

.island-body {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    /* The panel never scrolls itself — its content owns the scroll. */
    overflow: hidden;
}
</style>
