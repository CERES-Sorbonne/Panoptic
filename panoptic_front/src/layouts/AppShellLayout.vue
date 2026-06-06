<script setup lang="ts">
// Pure IDE shell frame (PyCharm "island" style): a top toolbar and a left
// activity bar that live on the tinted canvas, an inset work area where
// islands float, and a flush status bar. Content-blind — slots only.
interface Props {
    gap?: number
    activityWidth?: number
    toolbarHeight?: number
    statusHeight?: number
}

withDefaults(defineProps<Props>(), {
    gap: 6,
    activityWidth: 40,
    toolbarHeight: 40,
    statusHeight: 24
})
</script>

<template>
    <div class="shell">
        <div class="shell-toolbar" :style="{ height: toolbarHeight + 'px' }">
            <slot name="toolbar"></slot>
        </div>

        <div class="shell-body">
            <div class="shell-activity" :style="{ width: activityWidth + 'px' }">
                <slot name="activity"></slot>
            </div>
            <div class="shell-content" :style="{ padding: gap + 'px' }">
                <slot></slot>
            </div>
        </div>

        <div class="shell-status" :style="{ height: statusHeight + 'px' }">
            <slot name="statusbar"></slot>
        </div>
    </div>
</template>

<style scoped>
.shell {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    background-color: var(--island-canvas);
    box-sizing: border-box;
}

.shell-toolbar {
    display: flex;
    align-items: center;
    flex-shrink: 0;
}

.shell-body {
    display: flex;
    flex: 1;
    min-height: 0;
    overflow: hidden;
}

.shell-activity {
    display: flex;
    flex-shrink: 0;
}

.shell-content {
    display: flex;
    flex: 1;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
}

.shell-status {
    display: flex;
    align-items: center;
    flex-shrink: 0;
}
</style>
