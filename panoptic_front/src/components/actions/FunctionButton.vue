<script setup lang="ts">
import { ref } from 'vue';
import { ActionContext, ExecuteActionPayload } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import { usePanopticStore } from '@/data/panopticStore';

const project = useProjectStore()
const panoptic = usePanopticStore()

const props = defineProps<{
    fnc: string
    context: ActionContext
}>()
const emits = defineEmits(['instances', 'groups'])

const loading = ref(false)

async function call() {
    if (loading.value) return

    loading.value = true
    try {
        const req: ExecuteActionPayload = { function: props.fnc, context: props.context }
        const res = await project.call(req)

        if(res.notifs) {
            panoptic.notify(res.notifs)
        }

        if (res.groups) {
            emits('groups', res.groups)
        }
        if (res.instances) {
            emits('instances', res.instances)
        }
    } catch (e) {

    }
    loading.value = false
}
</script>

<template>
    <div class="d-flex flex-center">
        <div v-if="loading" class="spinner-border spinner-border-sm text-primary me-1" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
        <div class="bbb" @click="call">{{ props.fnc }}</div>
    </div>
</template>

<style scoped>
</style>