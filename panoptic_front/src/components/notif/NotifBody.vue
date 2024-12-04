<script setup lang="ts">
import { Notif } from '@/data/models';
import NotifIcon from './NotifIcon.vue';
import '@anilkumarthakur/vue3-json-viewer/styles.css';
import { JsonViewer } from '@anilkumarthakur/vue3-json-viewer';

const props = defineProps<{
    notif: Notif
}>()
const emits = defineEmits([])

</script>

<template>
    <div class="d-flex flex-column">
        <div>Received At: {{ props.notif.receivedAt.toLocaleString() }}</div>
        <div>Type: <span class="">
                <NotifIcon :type="props.notif.type" />
            </span> {{ props.notif.type }}</div>
        <div>Name: {{ props.notif.name }}</div>
        <div>Message: {{ props.notif.message }}</div>
        <div v-if="props.notif.data">Data: <br />
            <JsonViewer :data="props.notif.data" :dark-mode="false" style="font-family: monospace;" />
        </div>
    </div>
</template>

<style>
.notif-body {
    word-break: break-all;
}

.key {
    font-size: inherit;
}
</style>