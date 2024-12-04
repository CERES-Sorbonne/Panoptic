<script setup lang="ts">
import { ModalId, NotifType } from '@/data/models';
import Modal2 from './Modal2.vue';
import { useProjectStore } from '@/data/projectStore';
import { computed, nextTick, ref, watch } from 'vue';
import NotifPreview from '../notif/NotifPreview.vue';
import NotifBody from '../notif/NotifBody.vue';
import NotifIcon from '../notif/NotifIcon.vue';
import { useModalStore } from '@/data/modalStore';
import { usePanopticStore } from '@/data/panopticStore';

const panoptic = usePanopticStore()
const modal = useModalStore()

const selectedNotifId = ref(null)
const typeList = ref([NotifType.DEBUG, NotifType.INFO, NotifType.WARNING, NotifType.ERROR])
const selectedNotif = computed(() => panoptic.notifs.find(n => n.id == selectedNotifId.value))

const previewElems = ref({})

const notifFilter = ref({
    [NotifType.DEBUG]: true
})

const readFilter = ref(false)

const filteredNotifs = computed(() => panoptic.notifs.filter(n => (!notifFilter.value[n.type] && (!n.read || !readFilter.value)) || n.id == selectedNotifId.value))

function iconStyle(type: NotifType) {
    if (notifFilter.value[type]) {
        return 'dimmed'
    }
    return ''
}

function toggleFilter(type: NotifType) {
    if (notifFilter.value[type]) {
        delete notifFilter.value[type]
    } else {
        notifFilter.value[type] = true
    }
}

async function readNotif(id: number, scroll?: boolean) {
    selectedNotifId.value = id
    selectedNotif.value.read = true


    await nextTick()
    if (scroll && previewElems.value[id]) {
        previewElems.value[id].scrollIntoView()
    }
}

function toggleReadFilter() {
    readFilter.value = !readFilter.value

}

function onShow() {
    const notifId = useModalStore().getData(ModalId.NOTIF)
    if (notifId !== undefined) {
        readNotif(notifId, true)
    }
    else if (selectedNotif.value === undefined) {
        let last = filteredNotifs.value.length - 1
        readNotif(filteredNotifs.value[last].id)
    }
}

watch(() => modal.getData(ModalId.NOTIF), (newValue, oldValue) => {
    // readNotif(newValue)
})

</script>

<template>
    <Modal2 :id="ModalId.NOTIF" :layer="1" :max-width="800" :max-height="400" @show="onShow">
        <template #title>
            <span v-for="typ in typeList" class="bb" :class="iconStyle(typ)" @click="toggleFilter(typ)">
                <NotifIcon :type="typ" />
            </span>
            <span style="border-left: 1px solid var(--border-color); margin: 0 1px;"></span>
            <span class="bb" :class="readFilter ? '' : 'dimmed'" @click="toggleReadFilter()">
                <i class="bi bi-circle-fill text-primary"
                    style="font-size: 8px; position: relative; top: -3px; left:0px; margin: 0 2px" />
            </span>
            <b class="ps-1" style="border-left: 1px solid var(--border-color); margin-left: 1px;">Notification
                Center</b>
        </template>
        <template #content="{ data }">
            <div class="d-flex h-100" style="border-top: 1px solid var(--border-color)">
                <div class="d-flex flex-column notif-list flex-shrink-0">
                    <template v-for="notif in filteredNotifs">
                        <div @click="readNotif(notif.id)" :class="selectedNotifId == notif.id ? 'selected' : ''"
                            :ref="e => previewElems[notif.id] = e">
                            <NotifPreview :notif="notif" />
                        </div>
                    </template>
                </div>
                <div v-if="selectedNotif" class="p-2 notif-body">
                    <NotifBody :notif="selectedNotif" />
                </div>
            </div>
        </template>
    </Modal2>
</template>

<style scoped>
.notif-list {
    width: 200px;
    overflow-y: auto;
    overflow-x: hidden;
    height: 100%;
    background-color: rgb(239, 239, 239);
    border-right: 1px solid var(--border-color);
}

.notif-body {
    min-width: 300px;
    overflow-y: auto;
    overflow-x: hidden;
}

.selected {
    background-color: white;
}

.dimmed {
    opacity: 0.4;
}

.hover:hover {
    opacity: 1;
}
</style>