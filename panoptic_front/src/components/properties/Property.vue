<script setup>
import {computed} from 'vue'
import PropertyIcon from './PropertyIcon.vue';
import { globalStore } from '@/data/store';
import { PropertyMode } from '@/data/models';

const props = defineProps({
    data: Object,
})

const type = computed(() => props.data.type)
const visible = computed(() => globalStore.getPropertyVisible(props.data.id))

function toggleVisible() {
    globalStore.setPropertyVisible(props.data.id, !visible.value)
}
</script>

<template>
    <div class="property">
        <PropertyIcon :type="type" />
        {{ props.data.name}}

        <span class="float-end me-3">
            <!-- <span class="h6 bi bi-pencil btn-icon me-3"></span> -->
            <i v-if="props.data.mode == PropertyMode.sha1" class="bi bi-link-45deg me-2"></i>
            <span @click="toggleVisible" :class="'bi bi-eye btn-icon text-' + (visible ? 'primary' : 'secondary')"></span>
        </span>
    </div>
</template>

<style scoped="true">
.property{
    overflow-wrap: anywhere;
}
</style>