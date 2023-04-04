<script setup>
import {computed} from 'vue'
import PropertyIcon from './PropertyIcon.vue';

const props = defineProps({
    data: Object,
})

const type = computed(() => props.data.type)

</script>

<template>
    <h5>
        <PropertyIcon :type="type" />

        [{{props.data.type}}] 
        {{ props.data.name}}

        <span class="float-end">
            <span class="h6 bi bi-pencil btn-icon me-3"></span>
            <span @click="props.data.show = !props.data.show" :class="'h5 bi bi-eye btn-icon text-' + (props.data.show ? 'primary' : 'secondary')"></span>
        </span>
    </h5>
</template>

