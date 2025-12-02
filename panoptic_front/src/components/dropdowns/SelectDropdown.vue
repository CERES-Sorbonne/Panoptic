<script setup lang="ts">
import { computed } from 'vue'

import Dropdown from '../dropdowns/Dropdown.vue' 
import wTT from '../tooltips/withToolTip.vue' 

export interface SelectOption {
    value: string | number
    label?: string
    description?: string
    disabled?: boolean
    icon?: string
}

const props = defineProps<{
    options: SelectOption[]
    modelValue?: string | number | null
    placeholder?: string
    size?: number
    width?: number
    noBorder?: boolean
}>()

const emit = defineEmits<{
    (e: 'update:modelValue', value: string | number): void
    (e: 'changed', value: string | number): void 
}>()

const selectedOption = computed(() => {
    return props.options.find(option => option.value === props.modelValue)
})

const fontSize = computed(() => props.size ? props.size : 14)

const selectOption = (option: SelectOption, hide: () => void) => {
    if (option.disabled) return
    
    emit('update:modelValue', option.value)
    emit('changed', option.value)
    
    hide()
}

const capitalizeFirst = (text: any) => {
    return text.charAt(0).toUpperCase() + text.slice(1)
}
</script>

<template>
    <Dropdown placement="bottom-start" class="w-100" :teleport="true">
        
        <template #button>
            <div :style="{ fontSize: fontSize + 'px' }" style="white-space: nowrap;" class="w-100" :class="{'sbb': !props.noBorder, 'sb': props.noBorder}">
                
                <!-- Case 1: Nothing selected OR no options available -->
                <div v-if="!selectedOption" class="display placeholder-display display-flex">
                    <span class="display-text">{{ capitalizeFirst(placeholder ?? 'Select Option') }}</span>
                    <!-- Only show chevron if there are options to open -->
                    <i v-if="options.length > 0" class="bi bi-chevron-down" />
                </div>
                
                <!-- Case 2: An option is selected and has a description (uses ToolTip) -->
                <wTT v-else-if="selectedOption.description" :message="selectedOption.description" :style="{width:props.width+'px'}" class="display-container">
                    <div class="display display-flex">
                        <span class="display-text">
                            <span v-if="selectedOption.icon" :class="'bi bi-' + selectedOption.icon" class="me-1"></span>
                            <span class="display-label">{{ capitalizeFirst(selectedOption.label ?? selectedOption.value) }}</span>
                        </span>
                        <i class="bi bi-chevron-down" />
                    </div>
                </wTT>

                <!-- Case 3: An option is selected but no description (simple span) -->
                <div v-else class="display display-flex display-container" :style="{width:props.width+'px'}">
                    <span class="display-text">
                        <span v-if="selectedOption.icon" :class="'bi bi-' + selectedOption.icon" class="me-1"></span>
                        <span class="display-label">{{ capitalizeFirst(selectedOption.label ?? selectedOption.value) }}</span>
                    </span>
                    <i class="bi bi-chevron-down" />
                </div>

            </div>
        </template>
        
        <template #popup="{ hide }">
            <div class="">
                <div v-for="option in options" :key="option.value" style="white-space: nowrap;"
                    :class="['bb', { 'is-selected': option.value === modelValue, 'is-disabled': option.disabled }]"
                    @click="selectOption(option, hide)">
                    <span v-if="option.icon" :class="'bi bi-' + option.icon" class="me-2"></span>
                    <wTT v-if="option.description" :message="option.description">
                        {{ capitalizeFirst(option.label ?? option.value)}}
                    </wTT>
                    <span v-else>{{ capitalizeFirst(option.label ?? option.value) }}</span>
                </div>
                
                <div v-if="options.length === 0" class="text-gray-500 p-2 text-sm">
                    No options available
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.is-selected {
    background-color: var(--grey);
}

.is-disabled {
    color: #999;
    cursor: not-allowed;
    background-color: #f5f5f5;
}

.placeholder-display {
    color: #999;
}

.bb {
    /* text-transform: capitalize; */
    padding: 2px 4px;
    cursor: pointer;
    transition: background-color 0.1s;
}

.bb:not(.is-disabled):hover {
    background-color: #f0f0f0;
}

.display-flex {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
}

.display-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
}

.display-container {
    overflow: hidden;
}

.bi-chevron-down {
    flex-shrink: 0;
}
</style>