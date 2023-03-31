<script setup>
import {ref, computed, reactive} from 'vue'
import {PropertyType} from '@/data/models'

const props = defineProps({
    data: Object,
})

const type = computed(() => props.data.type)

</script>

<template>
    <h5>
        <i v-if="type == PropertyType.string" class="bi bi-type"></i>
        <i v-if="type == PropertyType.number" class="bi bi-123"></i>
        <i v-if="type == PropertyType.date" class="bi bi-calendar-date"></i>
        <i v-if="type == PropertyType.path" class="bi bi-code-slash"></i>
        <i v-if="type == PropertyType.image_link" class="bi bi-card-image"></i>
        <i v-if="type == PropertyType.url" class="bi bi-globe"></i>
        <i v-if="type == PropertyType.color" class="bi bi-palette"></i>
        <i v-if="type == PropertyType.checkbox" class="bi bi-check-square"></i>

        [{{props.data.type}}] 
        {{ props.data.name}}

        <span class="float-end">
            <span class="h6 bi bi-pencil btn-icon me-3"></span>
            <span @click="props.data.show = !props.data.show" :class="'h5 bi bi-eye btn-icon text-' + (props.data.show ? 'primary' : 'secondary')"></span>
        </span>
    </h5>
</template>

