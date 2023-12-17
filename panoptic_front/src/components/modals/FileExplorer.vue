<script setup>
import { ref, onMounted, onUpdated, computed } from 'vue';
import FileItem from './FileItem.vue';
import axios from 'axios'

const columns = ref([]);
const scrollContainer = ref(null);
const activeFolder = ref('')

const fetchFiles = async (path) => {
    let res = await axios.get('http://localhost:8000' + path)
    return res.data
};

const handleItemClick = async (file, columnId) => {
    if (columnId < columns.value.length - 1) {
        columns.value = columns.value.slice(0, columnId + 1)
    }
    if (!file.active) {
        columns.value[columnId] = columns.value[columnId].map(f => ({ ...f, active: f.name === file.name }))
        activeFolder.value = file
    }
    if (file.active) {
        file.active = false
    }
    if (file.extension === 'dir' || file.extension === 'disk') {
        const files = await fetchFiles(`/index?path=${file.path}`)
        if (files.length > 0) {
            columns.value.push(sortFiles(files))
        }
    }
};

onMounted(async () => {
    columns.value.push(sortFiles(await fetchFiles('/index')));
});

onUpdated(() => {
    scrollContainer.value.scrollLeft = scrollContainer.value.scrollWidth;
});

const sortFiles = (list) => {
    // Triez la liste pour afficher les éléments "disk" d'abord, puis les éléments "dir"
    return list.sort((a, b) => {
        if (a.extension === 'disk' && b.extension !== 'disk') {
            return -1;
        } else if (a.extension !== 'disk' && b.extension === 'disk') {
            return 1;
        } else if (a.extension === 'dir' && b.extension !== 'dir') {
            return -1;
        } else if (a.extension !== 'dir' && b.extension === 'dir') {
            return 1;
        } else {
            return a.name.localeCompare(b.name);
        }
    });
};

const addFolder = () => {
    console.log(activeFolder.path)
}
</script>

<template>
    <div class="row">
        <div class="col-9 mt-4" style="margin-left:0;overflow-x: auto;max-height: 75vh;min-height: 75vh;" ref="scrollContainer">
            <div class="row" style="flex-wrap: nowrap;">
                <!-- Colonnes suivantes pour les appels suivants -->
                <div v-for="(column, columnId) in columns" :key="column" class="col-auto" style="max-width: 23vw;">
                    <div v-if="columnId == 0" class="row">
                        <ul class="list-group">
                            <li class="list-group-item header">
                                <i class="bi bi-hdd"></i>
                                Disques
                            </li>
                            <FileItem v-for="file in column.filter(el => el.extension === 'disk')" :key="file.path" :file="file"
                                @itemClicked="handleItemClick(file, columnId)">
                            </FileItem>
                        </ul>
                        <ul class="list-group mt-3">
                            <li class="list-group-item header">
                                <i class="bi bi-house"></i>
                                Documents
                            </li>
                            <FileItem v-for="file in column.filter(el => el.extension === 'dir')" :key="file.path" :file="file"
                                @itemClicked="handleItemClick(file, columnId)">
                            </FileItem>
                        </ul>
                    </div>
                    <ul v-else class="list-group">
                        <FileItem v-for="file in column" :key="file.path" :file="file" :isLast="columnId === columns.length - 1"
                            @itemClicked="handleItemClick(file, columnId)">
                        </FileItem>
                    </ul>
                </div>
            </div>
        </div>
        <div class="images col-3">
            <img v-for="url in activeFolder.images_url" :src="'http://localhost:8000/images/' + url" class="mini"/>
        </div>
    </div>
    <div class="row mt-3">
        <div class="col-12">
            <div class="input-group">
                <input v-model="activeFolder.path" class="form-control" readonly>
                <button @click="addFolder" class="btn btn-primary">{{ $t('modals.add_folder.add') }}</button>
            </div>
        </div>
    </div>
</template>
  
<style scoped>
.header {
    background-color: #c3cfd9 !important;
    color: rgb(50, 50, 50);
}

.images {
    max-height: 75vh;
    overflow-y: scroll;
}
.mini {
    max-width: 75px;
}
</style>
 