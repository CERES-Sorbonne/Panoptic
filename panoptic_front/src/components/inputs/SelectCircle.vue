<!-- SelectCircle compenent used for image selection -->
<!-- The different style are meant to be used for the GroupLines and ImageUnique / ImagePile  -->


<script setup lang="ts">
import { computed, ref } from 'vue';

const props = defineProps({
    modelValue: Boolean,
    lightMode: Boolean,
    small: Boolean
})

// const selected = ref(false)
const hover = ref(false)

const emits = defineEmits(['update:modelValue'])

const circleClass = computed(() => {
    let base = props.small ? 'small-offset' : 'offset'

    if (props.modelValue) {
        return [base, 'text-primary']
    }
    if (hover.value && props.lightMode) {
        return [base, 'light-hover']
    }
    if (hover.value) {
        return [base, 'text-secondary']
    }
    else {
        return [base, 'icon-idle']
    }
})

function toggleSelect() {
    if (props.modelValue) {
        emits('update:modelValue', false)

    } else {
        emits('update:modelValue', true)
    }
}

</script>

<template>
    <div class="btn-icon" :class="circleClass" @mouseenter="hover = true" @mouseleave="hover = false">
        <i v-if="!props.modelValue" class="bi bi-check-circle-fill" @click.stop="toggleSelect"></i>
        <i v-else class="bi bi-check-circle-fill" @click.stop="toggleSelect"></i>
    </div>
</template>

<style scoped>
.small-offset {
    margin-top: 3px;
    font-size: 15px;
}

.offset {
    margin-top: 2px;
    font-size: 18px;
}

.icon-idle {
    color: rgb(220, 220, 220);
}

.light-hover {
    color: rgb(255, 255, 255);
}

</style>