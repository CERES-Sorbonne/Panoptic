<script setup lang="ts">
import { ModalId } from '@/data/models';
import { usePanopticStore } from '@/data/panopticStore';
import { goNext } from '@/utils/utils';

const panoptic = usePanopticStore()

const emits = defineEmits(['create', 'import'])

function importPath(path: string) {
    if(!path) return
    
    emits('import', path)
}

function promptPath() {
    panoptic.showModal(ModalId.FOLDERSELECTION, { callback: importPath, mode: 'import' })
}

</script>

<template>
    <div class="create-option d-flex">
        <div class="flex-grow-1">
            <h6 class="create-title m-0"> {{$t('main.projects.create')}}</h6>
            <span class="create-explanation">{{$t('main.projects.create_details')}}</span>
        </div>
        <div id="create-project" class="create-btn highlight" @click="emits('create');goNext()">{{$t('main.projects.create_button')}}</div>
    </div>
    <div class="create-option d-flex">
        <div class="flex-grow-1">
            <h6 class="create-title m-0">{{$t('main.projects.import')}}</h6>
            <span class="create-explanation">{{$t('main.projects.import_details')}}</span>
        </div>
        <div class="create-btn" @click="promptPath">{{$t('main.projects.import_button')}}</div>
    </div>
</template>

<style scoped>
.create-option {
    text-align: left;
    padding-bottom: 10px;
    padding-top: 10px;
    border-bottom: 1px solid var(--border-color);
}

.create-btn {
    text-align: center;
    background-color: rgb(240, 240, 240);
    height: 36px;
    padding: 6px;
    border-radius: 8px;
    margin-top: 6px;
    width: 100px;
    cursor: pointer;
    color: rgb(45, 45, 45);
}

.create-btn:hover {
    background-color: rgb(227, 227, 255);
    color: black;
}

.highlight {
    background-color: rgb(170, 170, 255);
    color: white;
}

.create-title {
    font-size: 20px;
}

.create-explanation {
    font-size: 15px;
}
</style>