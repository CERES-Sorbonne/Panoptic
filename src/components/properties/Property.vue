<script setup>
import {ref, computed, reactive} from 'vue'
import { globalStore } from '../../data/store';
import ExpandOption from '../menu/ExpandOption.vue';
import TagTree from '../TagTree/TagTree.vue';
import MultiTagProperty from './TagProperty.vue';

const props = defineProps({
    data: Object,
})

</script>

<template>
    <ExpandOption title-size="h5" left-align="true">
        <template #name>{{ props.data.name }}</template>
        <template #icons>
            <span class="h6 bi bi-pencil btn-icon me-3"></span>
            <span class="h6 bi bi-eye btn-icon"></span>
        </template>
        <template #content>
            <slot name="property"></slot>
        </template>
    </ExpandOption>
</template>

