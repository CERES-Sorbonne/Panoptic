<script setup lang="ts">
import { ref, computed } from 'vue'
import { useDataStore } from '@/data/dataStore';
import { SelectOption } from '../dropdowns/SelectDropdown.vue';
import { useI18n } from 'vue-i18n';
import { Instance, MapGroup } from '@/data/models';
import Zoomable from '../Zoomable.vue';
import CenteredImage from '../images/CenteredImage.vue';

const { t } = useI18n()
const data = useDataStore()

const props = defineProps<{
    selectedMap: number | null
    colorOption: string
    groups: MapGroup[]
    images: Instance[]
    hoverImageId: number | undefined
}>()

const emits = defineEmits([
    'update:selectedMap', 'update:spatialFunction', 'update:colorOption',
    'clusters', 'hoverGroup', 'clickGroup'
])

const isCollapsed = ref(false)

const hoverImage = computed(() => data.instances[props.hoverImageId])

function toggleCollapse() {
    isCollapsed.value = !isCollapsed.value
}


</script>

<template>
    <div class="map-menu" :class="{ 'collapsed': isCollapsed }">
        <div class="toggle-header" @click="toggleCollapse">
            <i :class="isCollapsed ? 'bi bi-arrow-left-circle' : 'bi bi-arrow-right-circle'"></i>
        </div>
        <div v-if="!isCollapsed" class="text-center" style="position: relative; top: 1px">{{ $t("map.main_menu") }}</div>
        <div class="mb-2    "></div>
        <div class="image-container">
            <Zoomable v-if="hoverImage" :image="hoverImage" class="">
                <CenteredImage :image="hoverImage" :width="260" :height="200" style="margin-left: 10px;"/>
            </Zoomable>
        </div>

        <div class="menu-content mt-2" :class="{ 'hidden': isCollapsed }">
            <div v-if="props.groups.length" class="menu-section-card scrollable-section">
                <div class="section-title">
                    <span>{{ props.colorOption == 'property' ? $t("map.group_property") : $t("map.group_cluster") }}</span>
                    <span class="badge">{{ props.groups.length }}</span>
                </div>
                <div class="groups-list">
                    <div 
                        v-for="group in props.groups" 
                        :key="group.id" 
                        class="group-item"
                        @mouseover="emits('hoverGroup', { groupId: group.id, value: true })" 
                        @mouseleave="emits('hoverGroup', { groupId: group.id, value: false })" 
                        @click="emits('clickGroup', group)"
                    >
                        <div class="group-color" :style="{ backgroundColor: group.color }"></div>
                        <span class="group-name">{{ group.name }}</span>
                        <span class="group-count">{{ group.count }}</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.map-menu {
    position: relative;
    height: 100%;
    background: rgb(246, 247, 249);
    border-left: 1px solid #ddd;
    display: flex;
    flex-direction: column;
    /* transition: width 0.3s ease; */
    flex-shrink: 0;
    width: 280px;
    overflow: hidden;
    padding-top: 5px;
}

.map-menu.collapsed {
    width: 40px;
}

.toggle-header {
    position: absolute;
    left: 5px;
    /* padding: 10px; */
    cursor: pointer;
    font-size: 18px;
    text-align: start;
    /* color: #666; */
    opacity: 0.8;
    padding-left: 5px;
    /* flex-shrink: 0; */
    top: 5px;
    z-index: 10;
    
}

.toggle-header:hover { color: #000; }

.menu-content {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 0 10px 10px 10px;
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    opacity: 1;
    /* transition: opacity 0.3s ease; */
    pointer-events: auto;
}

.menu-content.hidden {
    opacity: 0;
    pointer-events: none;
}

.menu-section-card {
    background: white;
    border: 1px solid #eee;
    border-radius: 8px;
    padding: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    flex-shrink: 0;
}

.section-title {
    font-weight: 600;
    font-size: 12px;
    color: #888;
    text-transform: uppercase;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
}

.groups-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.group-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px;
    border-radius: 4px;
    cursor: pointer;
    /* transition: background 0.2s; */
}

.group-item:hover { background: #f0f0f0; }

.group-color {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    flex-shrink: 0;
}

.group-name { 
    flex: 1; 
    font-size: 13px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.group-count { 
    font-size: 11px; 
    color: #999;
    flex-shrink: 0;
}

.scrollable-section {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
}

.groups-list { 
    overflow-y: auto;
    flex: 1;
}

.image-container {
    margin: auto;
    width: 280px;
    height: 200px;
    /* background-color: green; */
}

/* Custom Scrollbar */
.groups-list::-webkit-scrollbar { width: 4px; }
.groups-list::-webkit-scrollbar-thumb { background: #ccc; border-radius: 2px; }
</style>