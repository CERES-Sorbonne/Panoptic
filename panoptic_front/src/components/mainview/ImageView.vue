<script setup lang="ts">
import { computed } from 'vue'

// Simulated image-visualisation grid: placeholder thumbnails standing in for
// the real image collection while building the base layout.
interface Props {
    count?: number
    size?: number
}

const props = withDefaults(defineProps<Props>(), {
    count: 60,
    size: 96
})

const thumbs = computed(() =>
    Array.from({ length: props.count }, (_, i) => ({
        id: i,
        hue: (i * 47) % 360
    }))
)
</script>

<template>
    <div class="image-view">
        <div class="grid" :style="{ '--thumb-size': size + 'px' }">
            <div
                v-for="t in thumbs"
                :key="t.id"
                class="thumb"
                :style="{ background: `linear-gradient(135deg, hsl(${t.hue} 55% 72%), hsl(${(t.hue + 40) % 360} 55% 58%))` }"
            >
                <span class="thumb-label">{{ t.id + 1 }}</span>
            </div>
        </div>
    </div>
</template>

<style scoped>
.image-view {
    flex: 1;
    min-width: 0;
    min-height: 0;
    overflow: auto;
}

.grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(var(--thumb-size), 1fr));
    gap: var(--spacing-sm);
    padding: var(--spacing-sm);
}

.thumb {
    position: relative;
    aspect-ratio: 1;
    border-radius: var(--radius-sm);
    box-shadow: var(--shadow-sm);
}

.thumb-label {
    position: absolute;
    left: 4px;
    bottom: 3px;
    font-size: 10px;
    color: rgba(255, 255, 255, 0.9);
    text-shadow: 0 1px 1px rgba(0, 0, 0, 0.3);
}
</style>
