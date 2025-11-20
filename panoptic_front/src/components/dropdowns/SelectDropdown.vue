<script setup lang="ts">
import { computed } from 'vue';

// Assuming your generic Dropdown component is imported here
// If it's located at '../dropdowns/Dropdown.vue' relative to where SelectDropdown is used,
// you might need to adjust the path based on where you place this new component.
import Dropdown from '../dropdowns/Dropdown.vue'; 
import wTT from '../tooltips/withToolTip.vue'; // Assuming this utility is available

// -------------------------------------------------------------------------
// 1. Typescript Interface for Options
// -------------------------------------------------------------------------

/**
 * Defines the structure for each item in the dropdown list,
 * similar to your original ActionConfig setup.
 */
export interface SelectOption {
    value: string | number
    label?: string
    description?: string // For tooltips
    disabled?: boolean
    icon?: string // boostrap icon key
}

// -------------------------------------------------------------------------
// 2. Component Props and Emits
// -------------------------------------------------------------------------

const props = defineProps<{
    /** The array of options to display. */
    options: SelectOption[];
    /** The currently selected value (v-model support). */
    modelValue: string | number | null;
    /** Placeholder text when nothing is selected. */
    placeholder?: string;
    /** Optional size for font styling */
    size?: number;
}>();

const emit = defineEmits<{
    (e: 'update:modelValue', value: string | number): void;
    /** Emitted when a selection is made */
    (e: 'changed', value: string | number): void; 
}>();

// -------------------------------------------------------------------------
// 3. Computed Properties
// -------------------------------------------------------------------------

/**
 * Finds the currently selected option object.
 */
const selectedOption = computed(() => {
    return props.options.find(option => option.value === props.modelValue);
});

/**
 * Determines the label and description for the main display button.
 */

const fontSize = computed(() => props.size ? props.size : 14)

// -------------------------------------------------------------------------
// 4. Logic
// -------------------------------------------------------------------------

/**
 * Handles selection of an option, updating the model and notifying listeners.
 * @param option The selected option object.
 * @param hide Function provided by the generic Dropdown to close the popup.
 */
const selectOption = (option: SelectOption, hide: () => void) => {
    if (option.disabled) return;
    
    // 1. Update the v-model binding
    emit('update:modelValue', option.value);
    
    // 2. Emit the change event
    emit('changed', option.value);
    
    // 3. Close the popup
    hide();
};
</script>

<template>
    <Dropdown placement="bottom-start">
        
        <template #button>
            <div :style="{ fontSize: fontSize + 'px' }" style="white-space: nowrap;">
                <wTT v-if="selectedOption.description" :message="selectedOption.description">
                    <span v-if="selectedOption.icon" :class="'bi bi-' + selectedOption.icon" class="me-0"></span>
                    <span class="display">
                        {{ selectedOption.label ?? selectedOption.value }}
                        <i class="ms-1 bi bi-chevron-down" />
                    </span>
                </wTT>
                <span v-else class="display">
                    <span v-if="selectedOption.icon" :class="'bi bi-' + selectedOption.icon" class="me-0"></span>
                    {{ selectedOption.label ?? selectedOption.value }}
                    <i class="ms-1 bi bi-chevron-down" />
                </span>
            </div>
        </template>
        
        <template #popup="{ hide }">
            <div class="p-0">
                <div v-for="option in options" :key="option.value" 
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
/*
    Since this component inherits styling from the generic Dropdown's structural elements 
    and uses global utility classes (bbb, bb, ms-1, p-2), 
    we only need specific selection styles here.
*/
.is-selected {
    /* Style for the currently selected item in the list */
    background-color: var(--grey)
    /* font-weight: bold; */
    /* color: #1890ff; */
}

.is-disabled {
    /* Style for disabled items */
    color: #999;
    cursor: not-allowed;
    background-color: #f5f5f5;
}

/* Ensure the 'bb' class provides standard item styling, 
   and override only when necessary */
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
    padding: 4px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    cursor: pointer;
    text-transform: capitalize;
}
</style>