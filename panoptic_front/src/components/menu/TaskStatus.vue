<script setup lang="ts">
import { TaskState } from '@/data/models';
import { computed } from 'vue';


const props = defineProps<{
    task: TaskState
}>()

const finished = computed(() => props.task.total - props.task.remain - props.task.computing)
const total = computed(() => props.task.total)

</script>

<template>
    <div class="text-center">
        {{ props.task.name }}
        <div class="w-100 text-center" style="font-size: 10px;">
            {{ finished }} / {{ total }} {{ $t('main.nav.tasks.done') }}
        </div>
        <div v-if="total > 0" class="progress" role="progressbar" aria-label="Example 1px high"
            aria-valuemin="0" aria-valuemax="100" style="height: 1px">
            <div class="progress-bar"
                :style="`width: ${finished / total * 100}%`">
            </div>
        </div>
    </div>
</template>

<style scoped></style>