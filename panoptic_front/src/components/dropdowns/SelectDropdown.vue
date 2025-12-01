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
</script>

<template>
    <Dropdown placement="bottom-start">
        
        <template #button>
            <div :style="{ fontSize: fontSize + 'px' }" style="white-space: nowrap;" class="sbb">
                
                <!-- Case 1: Nothing selected OR no options available -->
                <span v-if="!selectedOption" class="display placeholder-display">
                    {{ placeholder ?? 'Select Option' }}
                    <!-- Only show chevron if there are options to open -->
                    <i v-if="options.length > 0" class="ms-1 bi bi-chevron-down" />
                </span>
                
                <!-- Case 2: An option is selected and has a description (uses ToolTip) -->
                <wTT v-else-if="selectedOption.description" :message="selectedOption.description" :style="{width:props.width+'px'}" style="overflow: hidden; text-overflow: ellipsis;">
                    <span class="display">
                        <span v-if="selectedOption.icon" :class="'bi bi-' + selectedOption.icon" class="me-1"></span>
                        <span class="display-label">{{ selectedOption.label ?? selectedOption.value }}</span>
                        <i class="ms-1 bi bi-chevron-down" />
                    </span>
                </wTT>

                <!-- Case 3: An option is selected but no description (simple span) -->
                <div v-else class="display" style="overflow: hidden; text-overflow: ellipsis;" :style="{width:props.width+'px'}">
                    <span v-if="selectedOption.icon" :class="'bi bi-' + selectedOption.icon" class="me-1"></span>
                    <span class="display-label">{{ selectedOption.label ?? selectedOption.value }}</span>
                    <i class="ms-1 bi bi-chevron-down" />
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
                        {{ option.label ?? option.value}}
                    </wTT>
                    <span v-else>{{ option.label ?? option.value }}</span>
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
    text-transform: capitalize;
    padding: 2px 4px;
    cursor: pointer;
    transition: background-color 0.1s;
}

.bb:not(.is-disabled):hover {
    background-color: #f0f0f0;
}

.display {
    text-transform: capitalize;
}
</style>