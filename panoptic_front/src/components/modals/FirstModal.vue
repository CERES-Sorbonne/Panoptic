<script setup lang="ts">
import { ModalId, PluginAddPayload } from '@/data/models';
import Modal from './Modal.vue';
import { computed, nextTick, ref } from 'vue';
import { usePanopticStore } from '@/data/panopticStore';
import PanopticIcon from '../icons/PanopticIcon.vue';

const panoptic = usePanopticStore()

const isLoadingPlugin = ref(false)

const hasPanopticMlPlugin = computed(() => panoptic.serverState.plugins.some(p => p.sourceUrl && p.sourceUrl.includes('https://github.com/CERES-Sorbonne/PanopticML')))


async function installPlugin() {
    isLoadingPlugin.value = true
    await nextTick()
    const plugin: PluginAddPayload = { pluginName: 'PanopticML', gitUrl: 'https://github.com/CERES-Sorbonne/PanopticML' }
    await panoptic.addPlugin(plugin)
    isLoadingPlugin.value = false
}

</script>


<template>
    <Modal :id="ModalId.FIRSTMODAL" ref="modalElem">
        <template #title>
            <!-- {{ $t('modals.export.title') }} -->
        </template>
        <template #content>
            <div class="p-2 text-center">
                <div class="icon">
                    <PanopticIcon />
                </div>
                <h1 class="m-0 p-0">Panoptic</h1>
                <div>
                    {{ $t('modals.first.introduction')}}
                </div>
                <div class="mt-5 text-center">
                    <span v-if="!isLoadingPlugin && !hasPanopticMlPlugin" class="bb" @click="installPlugin">
                        <i class="bi bi-lightbulb"></i>
                        {{ $t('main.home.plugins.install_panoptic_ml') }}
                    </span>
                    <div v-if="isLoadingPlugin">
                        <div class="spinner-border spinner-border-sm text-primary ms-1" role="status">
                            <span class="visually-hidden">{{ $t('main.home.plugins.load') }}</span>
                        </div>
                        {{ $t('installing') }}
                    </div>
                    <div v-if="hasPanopticMlPlugin">{{ $t('installed') }}</div>

                </div>

            </div>
        </template>
    </Modal>
</template>

<style scoped></style>