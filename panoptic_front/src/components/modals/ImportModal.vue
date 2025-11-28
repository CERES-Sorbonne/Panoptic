<script setup lang="ts">
import { ModalId } from '@/data/models';
import { ref, watch } from 'vue';
import Modal2 from './Modal2.vue';
import PageWindow from '../utils/PageWindow.vue';
import DataImport from '../import/DataImport.vue';
import TagImport from '../import/TagImport.vue';

const pageElem = ref(null)

enum PAGE {
    Data = 'data',
    Tags = 'tags',
}

const options = ref(Object.values(PAGE))
const selectedPage = ref('')

// Reset to home screen when modal opens/closes if needed, 
// or keep state. Here we default to empty (menu) on load.
watch(selectedPage, (newVal) => {
    // Optional: logic when page changes
})

</script>

<template>
    <Modal2 :id="ModalId.IMPORT" ref="modalElem">
        <template #title>
            {{ $t('modals.import.title') }}
        </template>
        <template #content>
            <div class="h-100 overflow-hidden">
                <PageWindow :options="options" v-model:page="selectedPage" lang-key="modals.import">
                    
                    <template #default="{ page }">
                        <div v-if="page == ''" class="h-100 w-100">
                            <div class="d-flex flex-wrap h-100 justify-content-center">
                                
                                <div class="bb align-self-center m-4" style="width: 120px;"
                                    @click="selectedPage = PAGE.Data">
                                    <div class="border rounded p-2 text-center">
                                        <div><i class="bi bi-file-earmark-spreadsheet" style="font-size: 50px;" /></div>
                                        <div>{{$t('modals.import.data')}}</div>
                                    </div>
                                </div>

                                <div class="bb align-self-center m-4" style="width: 120px;"
                                    @click="selectedPage = PAGE.Tags">
                                    <div class="border rounded p-2 text-center">
                                        <div><i class="bi bi-tags" style="font-size: 50px;" /></div>
                                        <div>{{$t('modals.import.tags')}}</div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <DataImport v-if="page == PAGE.Data" />
                        <TagImport v-if="page == PAGE.Tags" />
                        
                    </template>
                </PageWindow>
            </div>
        </template>
    </Modal2>
</template>

<style scoped>

</style>