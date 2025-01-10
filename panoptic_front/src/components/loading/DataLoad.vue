<script setup lang="ts">
import { useDataStore } from '@/data/dataStore';
import LoadWheel from './LoadWheel.vue';
import Percentage from './Percentage.vue';

const data = useDataStore()
</script>

<template>
    <div v-if="data.loadState" class="center">
        <div class="text-start" style="display: inline-block; width: 200px; height: 300px;">
            <div>
                <!-- Properties -->
                <div class="d-flex text-secondary">
                    <div class="me-1" style="font-size: 14px;">Properties</div>
                    <LoadWheel class="me-2" :loading="!data.loadState.finishedProperty" />
                    <i v-if="data.loadState.finishedProperty" style="font-size: 14px;"
                        class="bi bi-check text-success" />
                </div>


                <!-- PropertyGroups -->
                <div class="d-flex text-secondary" style="font-size: 14px;">
                    <div class="me-1">PropertyGroups</div>
                    <LoadWheel class="me-2" :loading="!data.loadState.finishedPropertyGroups" />
                    <i v-if="data.loadState.finishedPropertyGroups" class="bi bi-check text-success" />
                </div>

                <!-- Tags -->
                <div class="d-flex text-secondary" style="font-size: 14px;">
                    <div class="me-1">Tags</div>
                    <LoadWheel class="me-2" :loading="!data.loadState.finishedTags" />
                    <i v-if="data.loadState.finishedTags" class="bi bi-check text-success" />
                </div>

                <!-- Instances -->
                <div class="d-flex text-secondary" style="font-size: 14px;">
                    <div class="me-1">Instances</div>
                    <LoadWheel class="me-2" :loading="!data.loadState.finishedInstance" />
                    <i v-if="data.loadState.finishedInstance" class="bi bi-check text-success" />
                    <Percentage :current="data.loadState.counterInstance" :max="data.loadState.maxInstance"
                        :force="data.loadState.finishedInstance" />
                </div>

                <!-- InstanceValues -->
                <div class="d-flex text-secondary" style="font-size: 14px;">
                    <div class="me-1">InstanceValues</div>
                    <LoadWheel class="me-2" :loading="!data.loadState.finishedInstanceValues" />
                    <i v-if="data.loadState.finishedInstanceValues" class="bi bi-check text-success" />
                    <Percentage :current="data.loadState.counterInstanceValue" :max="data.loadState.maxInstanceValue"
                        :force="data.loadState.finishedInstanceValues" />
                </div>

                <!-- ImageValues -->
                <div class="d-flex text-secondary" style="font-size: 14px;">
                    <div class="me-1">ImageValues</div>
                    <LoadWheel class="me-2" :loading="!data.loadState.finishedImageValues" />
                    <i v-if="data.loadState.finishedImageValues" class="bi bi-check text-success" />
                    <Percentage :current="data.loadState.counterImageValue" :max="data.loadState.maxImageValue"
                        :force="data.loadState.finishedImageValues" />
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.center {
    display: flex;
    justify-content: center;
    align-items: center;
}
</style>