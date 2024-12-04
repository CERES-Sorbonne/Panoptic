<script setup lang="ts">
import { Notif } from '@/data/models';
import NotifIcon from './NotifIcon.vue';

const props = defineProps<{
    notif: Notif
}>()
const emits = defineEmits([])

</script>

<template>
    <div class="d-flex flex-column">
        <div>Received At: {{ props.notif.receivedAt.toLocaleString() }}</div>
        <div>Type: <span class=""><NotifIcon :type="props.notif.type" /></span> {{ props.notif.type }}</div>
        <div>Name: {{ props.notif.name }}</div>
        <div>Message: {{ props.notif.message }}</div>
        <div v-if="props.notif.data" >Data: {{ props.notif.data }}</div>
    </div>
</template>

<style scoped>
.notif-body {
    word-break: break-all;
}
</style>