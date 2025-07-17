<script setup>
import { ref, defineProps, watch, nextTick, onMounted } from 'vue'

const props = defineProps({
    defaultOpen: {
        type: Boolean,
        default: false
    },
    maxHeight: {
        type: String,
        default: '300px'
    },
    scrollToEnd: {
        type: Boolean,
        default: false
    }
})

const isOpen = ref(props.defaultOpen)
function toggle() {
    isOpen.value = !isOpen.value
}

const contentRef = ref(null)

async function scrollToEndIfNeeded() {
    if (props.scrollToEnd) {
        await nextTick()
        if (contentRef.value) {
            contentRef.value.scrollTop = contentRef.value.scrollHeight
        }
    }
}

onMounted(() => {
    scrollToEndIfNeeded()
})

watch(isOpen, (val) => {
    if (val) {
        scrollToEndIfNeeded()
    }
})
</script>

<template>
    <div>
        <div class="d-flex align-items-center cursor-pointer bb" @click="toggle" :aria-expanded="isOpen" role="button">
            <i :class="[
                'bi',
                isOpen ? 'bi-caret-down-fill' : 'bi-caret-right-fill',
                'me-2'
            ]"></i>
            <slot name="title"></slot>
        </div>
        <div
            v-show="isOpen"
            class="mt-1 collapsable-content"
            :style="{ maxHeight: props.maxHeight+'px' }"
            ref="contentRef"
        >
            <slot name="content"></slot>
        </div>
    </div>
</template>

<style scoped>
.cursor-pointer {
    cursor: pointer;
}
.collapsable-content {
    overflow-y: auto;
}
</style>
