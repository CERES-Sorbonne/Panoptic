<script setup lang="ts">
// Function picker + parameter form + cancel/call bar of an action. Shared by the
// dropdown and the view-modal presentations of ActionButton2.
import { computed, ref } from 'vue'
import { ParamDescription } from '@/data/models'
import ParamInput from '../inputs/ParamInput.vue'
import { useActionStore } from '@/data/stores/actionStore'
import wTT from '@/components/tooltips/withToolTip.vue'
import { sourceFromFunction, objValues, isParamVisible } from '@/utils/utils'

const actions = useActionStore()

const props = defineProps<{
    action: string
    inputs: ParamDescription[]
    width?: number
}>()
const localFunction = defineModel<string>('func')
const emits = defineEmits(['call', 'cancel'])

const showFunctionSelect = ref(false)
const source = computed(() => sourceFromFunction(localFunction.value))
const available = computed(() =>
    objValues(actions.index).filter(a => a.hooks.includes(props.action)).map(a => a.id)
)

function selectFunction(func: string) {
    localFunction.value = func
    showFunctionSelect.value = false
}

defineExpose({ reset: () => { showFunctionSelect.value = false } })
</script>

<template>
    <div :style="{ width: props.width ? props.width + 'px' : '100%' }" style="overflow: hidden;" class="d-flex flex-column"
        @keydown.enter="emits('call')">
        <!-- Function Selection View -->
        <div v-if="showFunctionSelect">
            <div v-for="func in available" :class="['bb', { 'is-selected': func === localFunction }]"
                class="option" @click="selectFunction(func)">
                <wTT :message="actions.index[func].description">
                    <i class="bi bi-boxes me-1" />{{ actions.index[func].id }}
                </wTT>
            </div>
            <div v-if="available.length === 0" class="text-gray-500 p-2 text-sm">
                No options available
            </div>
        </div>

        <!-- Parameters View -->
        <div v-else>
            <div class="function-header" @click="showFunctionSelect = true">
                <wTT v-if="localFunction && actions.index[localFunction]" :message="actions.index[localFunction].description">
                    <i class="bi bi-boxes me-1" /><span>{{ localFunction }}</span>
                </wTT>
                <div class="flex-grow-1"></div>
                <i class="ms-1 bi bi-chevron-down" />
            </div>

            <div v-if="props.inputs.length" style="padding-left: 5px; padding-right: 5px; margin-bottom: 3px;">
                <form @submit.prevent="" class="params-grid mt-1">
                    <template v-for="input in props.inputs">
                        <ParamInput v-if="isParamVisible(input, props.inputs)" :input="input" :source="source" :max-width="200" />
                    </template>
                </form>
            </div>

            <div class="d-flex flex-center p-1 bar" :class="{ 'no-shadow': props.inputs.length == 0 }">
                <div class="flex-grow-1"></div>
                <div class="bb" @click="emits('cancel')">{{ $t('cancel') }}</div>
                <div class="bb" @click="emits('call')">{{ $t('call') }}</div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.params-grid {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 4px 4px;
    align-items: center;
    padding: 4px 4px;
}

.bar {
    display: flex;
    padding: 0px 8px;
    box-shadow: 0px 0px 2px 1px var(--border-color);
}

.no-shadow {
    box-shadow: none !important;
}

.function-header {
    display: flex;
    padding: 4px 8px;
    box-shadow: 0px 0px 2px 1px var(--border-color);
    cursor: pointer;
    font-size: 14px;
}

.is-selected {
    background-color: var(--grey);
}

.option {
    padding: 4px 7px;
}
</style>
