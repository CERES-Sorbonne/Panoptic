<script setup lang="ts">
import { defineProps, defineEmits, computed, ref, watch } from 'vue'
import Dropdown from './Dropdown.vue'
import { useProjectStore } from '@/data/projectStore'

const project = useProjectStore()
// const props = defineProps<{}>()
const emits = defineEmits([])
const flash = ref(false)

const maxShow = 5

const buttonStyle = computed(() => {
    if(flash.value) {
        return {backgroundColor: 'blue'}
    }
    return {backgroundColor: 'white'}
})

const undos = computed(() => [...project.data.history.undo].reverse().slice(0, maxShow))
const redos = computed(() => project.data.history.redo.slice(Math.max(project.data.history.redo.length - maxShow, 0)))

watch(() => project.status.onUndo, () => {
    console.log('changed')
    flash.value = true
    setTimeout(() => flash.value = false, 100)
})

</script>

<template>
    <Dropdown>
        <template #button>
            <div class="d-flex sb flash" style="font-size: 14px;" :style="buttonStyle">
                <i class="bi bi-clock-history me-1"></i>
                <div>{{ $t('dropdown.history.button') }}</div>
            </div>
        </template>
        <template #popup>
            <!-- {{ project.data.history }} -->
            <div class="p-2">
                <div v-if="project.data.history.redo.length > maxShow" class="border mb-1 p-1 text-center text-secondary"  style="background-color: #f7f7f7;" >
                    + {{ project.data.history.redo.length - maxShow }}
                </div>
                <div v-for="commit in redos" class="border mb-1 p-1">
                    <span class="me">{{ new Date(commit.timestamp).toLocaleTimeString('fr-Fr', { hour: '2-digit', minute: '2-digit' }) }}</span>
                    <span class="sep ms-1 me-1"></span>
                    <span v-if="commit.tags">{{ commit.tags }} {{ $t('dropdown.history.tags') }}</span>
                    <span v-if="commit.values">{{ commit.values }} {{ $t('dropdown.history.values') }}</span>
                </div>
                <div class="border mb-1 p-1"  style="background-color: #f7f7f7;" >
                    <div class="d-flex center justify-content-center">
                        <div v-if="undos.length" class="bi bi-arrow-down sb" @click="project.undo"></div>
                        <div v-else class="bi bi-arrow-down text-secondary"></div>
                        <div style="width: 30px;"></div>
                        <div v-if="redos.length" class="bi bi-arrow-up sb" @click="project.redo"></div>
                        <div v-else class="bi bi-arrow-up text-secondary"></div>
                    </div>
                </div>
                <div v-for="commit in undos" class="border mb-1 p-1">
                    <span class="me">{{ new Date(commit.timestamp).toLocaleTimeString('fr-Fr', { hour: '2-digit', minute: '2-digit' }) }}</span>
                    <span class="sep ms-1 me-1"></span>
                    <span v-if="commit.tags">{{ commit.tags }} {{ $t('dropdown.history.tags') }}</span>
                    <span v-if="commit.values">{{ commit.values }} {{ $t('dropdown.history.values') }}</span>
                </div>
                <div v-if="project.data.history.undo.length > maxShow" class="border mb-1 p-1 text-center text-secondary"  style="background-color: #f7f7f7;" >
                    + {{ project.data.history.undo.length - maxShow }}
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.flash {
  transition: background-color 0.5s ease;
}
</style>