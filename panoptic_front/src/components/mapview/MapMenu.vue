<script setup lang="ts">
import { defineProps, defineEmits, ref, nextTick, computed } from 'vue'
import ActionSelectButton from '../actions/ActionSelectButton.vue';
import PointMapSelection from './PointMapSelection.vue';
import ActionButton2 from '../actions/ActionButton2.vue';
import { useDataStore } from '@/data/dataStore';
import SelectDropdown, { SelectOption } from '../dropdowns/SelectDropdown.vue';
import { useI18n } from 'vue-i18n';
const { t } = useI18n()
const data = useDataStore()

const props = defineProps<{
    selectedMap: number | null
    showImages: boolean
    showPoints: boolean
    baseImageSize: number
    maxImageSize: number
    minImageSize: number
    spatialFunction: {
        function: string
        context: any
    }
    colorOption: string
}>()

const emits = defineEmits([
    'update:selectedMap',
    'update:showImages',
    'update:showPoints',
    'update:baseImageSize',
    'update:maxImageSize',
    'update:minImageSize',
    'update:spatialFunction',
    'update:colorOption',
    'result',
    'colorGroups'
])

const isCollapsed = ref(false)
const showContent = ref(true)

const colorOptions = computed<SelectOption[]>(() => {
    return [
        { value: 'property', label: t('map.color_prop'), icon: 'stack' },
        { value: 'cluster', label: t('map.color_cluster'), icon: 'stack' }
    ]
})

// Fake data for demonstration
const fakeGroups = ref([
    { id: 1, name: 'Landscapes', color: '#FF6B6B', count: 45 },
    { id: 2, name: 'Portraits', color: '#4ECDC4', count: 32 },
    { id: 3, name: 'Architecture', color: '#45B7D1', count: 28 },
    { id: 4, name: 'Nature', color: '#96CEB4', count: 67 },
    { id: 5, name: 'Urban', color: '#FFEAA7', count: 19 },
    { id: 6, name: 'Abstract', color: '#DFE6E9', count: 54 },
    { id: 7, name: 'Wildlife', color: '#00B894', count: 41 },
    { id: 8, name: 'Street Photography', color: '#FDCB6E', count: 23 },
    { id: 9, name: 'Macro', color: '#E17055', count: 38 },
    { id: 10, name: 'Black & White', color: '#2D3436', count: 56 },
    { id: 11, name: 'Food', color: '#FD79A8', count: 15 },
    { id: 12, name: 'Travel', color: '#A29BFE', count: 72 },
    { id: 13, name: 'Sports', color: '#74B9FF', count: 29 },
    { id: 14, name: 'Events', color: '#FAB1A0', count: 33 },
    { id: 15, name: 'Experimental', color: '#6C5CE7', count: 18 },
])

function toggleCollapse() {
    if (isCollapsed.value) {
        // === EXPANDING ===
        isCollapsed.value = false
        setTimeout(() => {
            showContent.value = true
        }, 300)
    } else {
        // === COLLAPSING ===
        showContent.value = false
        nextTick(() => {
            isCollapsed.value = true
        })
    }
}

function handleSpatialFunctionChange(e: any) {
    emits('update:spatialFunction', e)
}

function handleResult(res: any) {
    emits('result', res)
}

function handleColorGroups() {
    emits('colorGroups')
}
</script>

<template>
    <div class="map-menu" :class="{ 'collapsed': isCollapsed }">
        <!-- Collapse/Expand Button -->
        <div class="collapse-btn bb text-center d-flex" @click="toggleCollapse"
            :title="isCollapsed ? 'Expand Menu' : 'Collapse Menu'">
            <div class="text-center" :class="{ 'btn-small': isCollapsed }">
                <i class="bi" :class="isCollapsed ? 'bi-chevron-right' : 'bi-chevron-left'"></i>
            </div>
            <div v-if="!isCollapsed" class="ms-2"></div>
        </div>

        <!-- Menu Content -->
        <div class="menu-content" v-if="showContent">
            <!-- Map Selection Section -->
            <div class="menu-section-card">
                <div class="section-title">Visualisation</div>
                <div v-if="data.hasMaps" class="menu-section-full" style="">
                    <PointMapSelection :model-value="selectedMap"
                        @update:model-value="$emit('update:selectedMap', $event)" />
                </div>

                <div class="menu-section m-0 p-0">
                    <ActionButton2 action="map" class="bb ps-1" style="font-size: 14px;">
                        <i class="bi bi-boxes" /> {{ $t('map.create') }}
                    </ActionButton2>
                </div>

                <template v-if="!selectedMap">
                    <span class="text-secondary help-text">{{ $t('map.no_map_help') }}</span>
                </template>
            </div>

            <!-- Display Options Section (only when map selected) -->
            <div class="menu-section-card" v-if="selectedMap">
                <div class="section-title">Display Options</div>
                <div class="menu-section">
                    <div class="checkbox-item sb">
                        <input type="checkbox" :checked="showImages"
                            @change="$emit('update:showImages', ($event.target as HTMLInputElement).checked)"
                            id="showImages" />
                        <label for="showImages" class="w-100">Show Images</label>
                    </div>
                    <div class="checkbox-item sb">
                        <input type="checkbox" :checked="showPoints"
                            @change="$emit('update:showPoints', ($event.target as HTMLInputElement).checked)"
                            id="showPoints" />
                        <label for="showPoints" class="w-100">Show Points</label>
                    </div>
                    <div class="">
                        <SelectDropdown :options="colorOptions" :model-value="props.colorOption" @update:model-value="e => emits('update:colorOption', e)" :no-border="true"/>
                    </div>
                    <div v-if="props.colorOption == 'cluster'" class="sb">
                        <ActionButton2 action="group"><i class="bi bi-boxes me-1" />{{ $t('map.action_cluster') }}</ActionButton2>
                    </div>
                </div>
            </div>

            <!-- Groups Section (Scrollable) - ALWAYS VISIBLE -->
            <div class="menu-section-card scrollable-section">
                <div class="section-title">
                    <span>Groups</span>
                    <span class="badge">{{ fakeGroups.length }}</span>
                </div>
                <div class="groups-list">
                    <div v-for="group in fakeGroups" :key="group.id" class="group-item">
                        <div class="group-color" :style="{ backgroundColor: group.color }"></div>
                        <span class="group-name">{{ group.name }}</span>
                        <span class="group-count">{{ group.count }}</span>
                    </div>
                </div>
            </div>

            <!-- Actions Section (only when map selected) -->
            <div class="menu-section-card" v-if="selectedMap">
                <button class="color-groups-btn" @click="handleColorGroups">
                    <i class="bi bi-palette"></i>
                    Color Groups
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.map-menu {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 6px;
    background: rgba(195, 207, 217, 0.219);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border-right: 1px solid rgba(195, 207, 217, 0.117);
    box-shadow: 0 0 2px 2px rgb(195, 207, 217);

    min-width: 220px;
    max-width: 280px;
    width: 280px;

    border-radius: 5px;
    font-size: 14px;

    overflow: hidden;
    white-space: nowrap;

    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.map-menu.collapsed {
    min-width: 30px;
    max-width: 30px;
    width: 30px;
    border: none;
    padding: 0;
}

.btn-small {
    width: 30px;
    text-align: center;
}

.menu-content {
    display: flex;
    flex-direction: column;
    gap: 8px;
    animation: fadeIn 0.3s ease-in-out;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
}

.menu-content::-webkit-scrollbar {
    width: 6px;
}

.menu-content::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.05);
    border-radius: 3px;
}

.menu-content::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 3px;
}

.menu-content::-webkit-scrollbar-thumb:hover {
    background: rgba(0, 0, 0, 0.3);
}

@keyframes fadeIn {
    from {
        opacity: 0;
    }

    to {
        opacity: 1;
    }
}

/* Card-style sections with glass effect */
.menu-section-card {
    background: rgba(255, 255, 255, 0.911);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.8);
    border-radius: 8px;
    padding: 6px 12px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    transition: all 0.2s;
    
}

.menu-section-card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.section-title {
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #495057;
    margin-bottom: 2px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.badge {
    background: rgba(0, 123, 255, 0.15);
    color: #007bff;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}

.scrollable-section {
    max-height: 300px;
    display: flex;
    flex-direction: column;
}

.groups-list {
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding-right: 4px;
}

.groups-list::-webkit-scrollbar {
    width: 5px;
}

.groups-list::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.03);
    border-radius: 3px;
}

.groups-list::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.15);
    border-radius: 3px;
}

.groups-list::-webkit-scrollbar-thumb:hover {
    background: rgba(0, 0, 0, 0.25);
}

.group-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    background: rgba(255, 255, 255, 0.5);
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
}

.group-item:hover {
    background: rgba(255, 255, 255, 0.8);
    transform: translateX(2px);
}

.group-color {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    flex-shrink: 0;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.group-name {
    flex: 1;
    font-size: 13px;
    color: #333;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.group-count {
    font-size: 11px;
    color: #6c757d;
    background: rgba(0, 0, 0, 0.05);
    padding: 2px 6px;
    border-radius: 10px;
    flex-shrink: 0;
}

.help-text {
    font-size: 12px;
    line-height: 1.4;
    margin-top: 4px;
}

.menu-section {
    display: flex;
    flex-direction: column;
}

.menu-section-full {
    display: flex;
    flex-direction: column;
    width: 100%;
}

.checkbox-item {
    display: flex;
    align-items: center;
    gap: 5px;
}

.checkbox-item input[type="checkbox"] {
    cursor: pointer;
}

.checkbox-item label {
    cursor: pointer;
    user-select: none;
}

.color-groups-btn {
    width: 100%;
    padding: 10px 12px;
    background: rgba(0, 123, 255, 0.85);
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 500;
    transition: all 0.2s;
    backdrop-filter: blur(5px);
    -webkit-backdrop-filter: blur(5px);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
}

.color-groups-btn i {
    font-size: 14px;
}

.color-groups-btn:hover {
    background: rgba(0, 86, 179, 0.95);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 123, 255, 0.3);
}

.color-groups-btn:active {
    background: rgba(0, 64, 133, 1);
    transform: translateY(0);
}
</style>