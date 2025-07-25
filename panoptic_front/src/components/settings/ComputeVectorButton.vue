<script setup lang="ts">
import { ref } from 'vue';
import { VectorType } from '@/data/models';
import { useActionStore } from '@/data/actionStore';

const props = defineProps<{
    vectorType: VectorType
}>()

const actions = useActionStore()
const loading = ref(false)

async function computeVectors() {
    loading.value = true
    await actions.callComputeVector(props.vectorType)
    loading.value = false
}
</script>

<template>
    <span @click="computeVectors" class="bb">
        <span v-if="loading" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
        <i v-else class="bi bi-database-add" />
    </span>
</template>

<style scoped></style>
