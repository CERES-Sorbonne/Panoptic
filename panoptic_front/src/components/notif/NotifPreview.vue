<script setup lang="ts">
import { Notif } from '@/data/models';
import NotifIcon from './NotifIcon.vue';

const props = defineProps<{
    notif: Notif
}>()
const emits = defineEmits([])

</script>

<template>
    <div class="d-flex notif-header position-relative">
        <div class="me-1 pe-1" style="border-right: 1px solid var(--border-color);">
            <NotifIcon :type="props.notif.type" />
        </div>
        <div>{{ props.notif.name }}</div>
        <div class="flex-grow-1"></div>
        <div v-if="!props.notif.read"><i class="bi bi-circle-fill text-primary"
                style="font-size: 8px; position: relative; top: -2px;" /></div>
    </div>
</template>

<style scoped>
.notif-header {
    padding: 2px;
    border-bottom: 1px solid var(--border-color);
    cursor: pointer;
    word-break: break-all;
}
</style>