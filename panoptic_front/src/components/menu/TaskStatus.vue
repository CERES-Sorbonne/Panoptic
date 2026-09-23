<script setup lang="ts">
import { TaskState } from '@/data/models';
import { computed } from 'vue';

const props = defineProps<{
    task: TaskState
}>()

const total = computed(() => props.task.total)
const done = computed(() => props.task.done)
const failed = computed(() => props.task.failed)
const progress = computed(() => total.value > 0 ? done.value / total.value * 100 : 0)
</script>

<template>
    <div class="text-center">
        {{ props.task.name }}
        <div class="w-100 text-center" style="font-size: 10px;">
            {{ done }} / {{ total }} {{ $t('main.nav.tasks.done') }}
            <span v-if="failed > 0" class="text-danger">({{ failed }} failed)</span>
        </div>
        <div v-if="total > 0" class="progress" role="progressbar"
            aria-valuemin="0" aria-valuemax="100" style="height: 1px">
            <div class="progress-bar" :style="`width: ${progress}%`" />
            <div v-if="failed > 0" class="progress-bar bg-danger"
                :style="`width: ${failed / total * 100}%`" />
        </div>
    </div>
</template>