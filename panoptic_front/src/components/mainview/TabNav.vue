<script setup lang="ts">
import { useI18n } from 'vue-i18n';
const { locale } = useI18n();
import wTT from '../tooltips/withToolTip.vue'
import { useProjectStore } from '@/data/projectStore';
import { ModalId } from '@/data/models';
import { usePanopticStore } from '@/data/panopticStore';
import { useTabStore } from '@/data/tabStore';
import TabButton from './TabButton.vue';

const panoptic = usePanopticStore()
const tabStore = useTabStore()


const props = defineProps<{
    reRender: Function
    filterOpen: boolean
}>()

const emits = defineEmits(['update:filterOpen'])

async function addTab(event: any) {
    await tabStore.addTab('New Tab')
}

const langs = ['fr', 'en']

function toggleFilter() {
    emits('update:filterOpen', !props.filterOpen)
}

function onChangeLang(event) {
    props.reRender()
    const lang = event.target.value;
    locale.value = lang;
    useProjectStore().setLang(lang)
}

</script>

<template>
    <nav>
        <div class="d-flex d-row" style="cursor: pointer;">
            <div class="pt-1"><span @click="toggleFilter">
                    <i v-if="props.filterOpen" class="bb bi bi-chevron-down" />
                    <i v-else class="bb bi bi-chevron-right" />
                </span> </div>
            <div v-for="tab in tabStore.loadedTabs">
                <TabButton :tab="tabStore.getTab(tab)" />
            </div>
            <wTT message="main.menu.add_tab_tooltip"><button class="tab-icon hover-light ps-1 pe-1" @click="addTab"
                    id="add-tab-button"><span class="bi bi-plus"></span></button></wTT>
            <div class="flex-grow-1"></div>
            <div style="padding-top: 2px; margin-right: 2px;">
                <wTT message="modals.notif.icon">
                    <span class="bb" @click="panoptic.showModal(ModalId.NOTIF)"><i class="bi bi-bell"></i></span>
                </wTT>
            </div>
            <div class="lang">
                <i class="bi bi-translate" style="margin-right:0.5rem"></i>
                <select :value="$i18n.locale" @change="onChangeLang">
                    <option v-for="(lang, i) in langs" :key="`Lang${i}`" :value="lang">
                        {{ lang.toUpperCase() }}
                    </option>
                </select>
            </div>
        </div>
    </nav>
</template>

<style>
.no-border {
    border: none !important;
}

.hidden {
    visibility: hidden;
}

.lang {
    margin-left: auto;
    order: 2;
    margin-top: 0.1em;
    margin-right: 0.5em;
    font-size: 16px
}
</style>