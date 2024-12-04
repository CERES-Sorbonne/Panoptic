<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';

const props = defineProps({
    leftAlign: Boolean,
    defaultExpand: { type: Boolean, default: true },
    resetOnHide: { type: Boolean, default: false },
    icon: { type: String, default: 'chevron' },
    fill: { type: String, default: '' }
});

const expand = ref(true);

const caretClass = computed(() => 'expand-icon bi-' + props.icon + '-right' + props.fill + ' clickable ' + (expand.value ? 'expand' : 'hide'))

function toggle() {
    expand.value = !expand.value;
}

onMounted(() => {
    if (props.defaultExpand !== undefined) {
        expand.value = props.defaultExpand
    }
})
</script>

<template>
    <div>
        <div>
            <span v-if="leftAlign" class="float-start me-2">
                <span :class="caretClass" @click.stop="toggle"></span>
            </span>
            <slot name="name"></slot>
            <span class="float-end">
                <span style="margin-right: 3px;">
                    <slot name="icons"></slot>
                </span>
                <span v-if="!props.leftAlign" :class="caretClass" @click.stop="toggle"></span>
            </span>
        </div>
        <!-- Use v-if to delete component n hide -->
        <template v-if="props.resetOnHide">
            <div v-if="expand" class="">
                <div class="">
                    <slot name="content"> </slot>
                </div>
            </div>
        </template>
        <!-- DEFAULT BEHAVIOR -->
        <!-- User v-show to keep the element in dom and just hiding it when needed -->
        <template v-else>
            <div v-show="expand" class="">
                <div class="">
                    <slot name="content"> </slot>
                </div>
            </div>
        </template>
    </div>
</template>

<style>
.expand-icon {
    display: inline-block;
    transition: 0.2s;
    margin-left: 0 !important;
}

.expand-icon.expand {
    transform: rotate(90deg) !important;
}

.expand-icon.hide {
    transform: rotate(0deg) !important;
}

.option-content {
    width: 100%
}
</style>
