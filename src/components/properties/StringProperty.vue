<script setup lang="ts">

import { reactive } from 'vue';
import TagTree from '../TagTree/TagTree.vue';
import Property from './Property.vue';

const props = defineProps({
    data: Object,
    filter: Object
})


</script>

<template>
    <Property :data="props.data">
        <template #property>
            Je sais pas quoi mettre ici
        </template>
    </Property>
    
</template>