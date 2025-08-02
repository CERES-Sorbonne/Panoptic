<script setup lang="ts">
import { onMounted } from 'vue'
import { usePanopticStore } from '@/data/panopticStore'
import { RouterView } from 'vue-router'
import { ModalId } from '@/data/models'
import PropertyModal from '@/components/modals/PropertyModal.vue'
import FolderSelectionModal from '@/components/modals/FolderSelectionModal.vue'
import ExportModal2 from '@/components/modals/ExportModal2.vue'
import ImageModal from '@/components/modals/ImageModal.vue'
import ImageZoomModal from '@/components/modals/ImageZoomModal.vue'
import SettingsModal from '@/components/modals/SettingsModal.vue'
import ImportModal from '@/components/modals/ImportModal.vue'
import TagModal from '@/components/modals/TagModal.vue'
import FirstModal from '@/components/modals/FirstModal.vue'
import NotifModal from '@/components/modals/NotifModal.vue'
import { useSocketStore } from '@/data/socketStore'
import UserSelection from '@/components/UserSelection.vue'

const socketStore = useSocketStore()
const panoptic = usePanopticStore()

onMounted(() => {
    socketStore.init()
    panoptic.init()
})
</script>

<template>
    <template v-if="!panoptic.isConnected">
        <div class="above">Lost connection to backend. Verify that panoptic is running and
            reload page</div>
    </template>
    <template v-else>
        <template v-if="!panoptic.isUserValid">
            <div><UserSelection :users="panoptic.serverState.users" @connect-user="u => socketStore.connectUser(u.id)"/></div>
        </template>
        <template v-else>
            <RouterView />
            <PropertyModal :id="ModalId.PROPERTY" />
            <FolderSelectionModal :id="ModalId.FOLDERSELECTION" />
            <ExportModal2 />
            <ImageModal />
            <ImageZoomModal />
            <SettingsModal />
            <ImportModal />
            <TagModal />
            <FirstModal />
            <NotifModal />
        </template>
    </template>
    <div id="popup" style="position: fixed; top:0;left: 0; z-index: 9990;"></div>
</template>

<style scoped>
.above {
    width: 100%;
    position: absolute;
    top: 50%;
    text-align: center;
    z-index: 200;
}

.above2 {
    position: absolute;
    top: 500px;
    left: 500px;
}
</style>
