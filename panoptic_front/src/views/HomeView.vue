<script setup lang="ts">
import { useSelectionStore } from '@/data/selectionStore';
import { useStore } from '@/data/store';
import router from '@/router';
import { computed, onMounted, reactive, ref } from 'vue';

const selectionStore = useSelectionStore()
const store = useStore()

interface Project {
    path: string
    name: string
}

const hasProjects = computed(() => Array.isArray(selectionStore.data.status.projects) && selectionStore.data.status.projects.length > 0)


onMounted(() => {
    if(selectionStore.isProjectLoaded) {
        router.push('/view')
    }
})

</script>

<template>
    <div class="window d-flex">
        <div v-if="hasProjects" class="project-menu">
            <div v-for="project in selectionStore.data.status.projects" class="d-flex">
                <div class="project flex-grow-1" @click="selectionStore.loadProject(project.path)">
                    <h5 class="m-0">{{ project.name }}</h5>
                    <div class="m-0 p-0 text-wrap text-break dimmed-2">{{project.path}}</div>
                </div>
                <div class="project-option flex-shrink-0">
                    <i class="bi bi-three-dots-vertical"></i>
                </div>
            </div>
        </div>
        <div class="main-menu flex-grow-1">
            <div class="icon">👀</div>
            <h1 class="m-0 p-0">Panoptic</h1>
            <h6 class="dimmed-2">Version pre-2.0</h6>

            <div class="create-menu mt-5 pt-5">
                <div class="create-option d-flex">
                    <div class="flex-grow-1">
                        <h6 class="create-title m-0">Créer un nouveau projet</h6>
                        <span class="create-explanation">Créer un nouveau projet panotpic dans un dossier.</span>
                    </div>
                    <div class="create-btn highlight">Créer</div>
                </div>
                <div class="create-option d-flex">
                    <div class="flex-grow-1">
                        <h6 class="create-title m-0">Importer un projet</h6>
                        <span class="create-explanation">Choisissez un dossier Panoptic existant.</span>
                    </div>
                    <div class="create-btn">Importer</div>
                </div>
                <div>
                </div>
            </div>
        </div>
    </div>
</template>

 <style scoped>


.dimmed-2 {
    color: rgb(90, 90, 90)
}

 .window {
    width: 100vw;
    height: 100vh;
 }

.project-menu {
    height: 100%;
    width: 350px;
    padding: 25px;
    padding-right: 0px;
    background-color: rgb(246, 246, 247);
    color: rgb(45, 45, 45);
    border-right: 1px solid var(--border-color);
}

.project {
    padding: 10px;
    cursor: pointer;
}

.project:hover {
    background-color: rgb(232, 232, 255);
    border-radius: 10px;
}


.main-menu {
    height: 100%;
    background-color: white;
    text-align: center;
    padding: 15px;
}

.project-option {
    width: 20px;
    margin: 0 15px;
    text-align: center;
    cursor: pointer;
}

.icon {
    font-size: 100px;
    line-height: 100px;
    margin-top: 50px;
}

.create-menu {
    /* background-color: green; */
    width: 500px;
    margin: auto;
}

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