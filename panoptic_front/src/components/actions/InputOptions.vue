<script setup lang="ts">
import { useActionStore } from '@/data/actionStore';
import { ParamDescription } from '@/data/models';
import { computed, onMounted, ref } from 'vue'
import Dropdown from '../dropdowns/Dropdown.vue';
import ParamInput from '../inputs/ParamInput.vue';
import wTT from '../tooltips/withToolTip.vue';

const actions = useActionStore()

const props = defineProps<{
    functionId: string
    size?: number
    hideText?: boolean
}>()
const emits = defineEmits(['changed'])

const localInputs = ref<ParamDescription[]>([])
const fontSize = computed(() => props.size ? props.size : 12)

const sourceName = computed(() => {
    return props.functionId.slice(0, props.functionId.indexOf('.'))
})

function loadInput() {
    if (!props.functionId) return
    if (!actions.index[props.functionId]) return
    
    const params = actions.index[props.functionId].params
    const defaults = actions.getContext(props.functionId).uiInputs

    for(let param of params) {
        param.defaultValue = defaults[param.name]
    }

    localInputs.value = JSON.parse(JSON.stringify(params))
}

async function submit() {
    for (let i in localInputs.value) {
        actions.index[props.functionId].params[i].defaultValue = localInputs.value[i].defaultValue
    }
    await actions.updateDefaultParams()
    emits('changed')
}

function cancel() {
    loadInput()
}

onMounted(loadInput)

</script>

<template>
    <div v-if="localInputs.length" :style="{ fontSize: fontSize + 'px' }">
        <Dropdown>
            <template #button>
                <div>
                    <wTT message="Options">
                        <span class="bbb"><i class="bi bi-gear" /></span>
                    </wTT>
                </div>
            </template>
            <template #popup="{ hide }">
                <form @submit.prevent="submit(); hide();" class="p-2">
                    <div v-for="input, i in localInputs" class="mb-1">
                        <ParamInput v-if="!(input.name == 'text' && props.hideText)" :input="input" :source="sourceName"/>
                    </div>
                    <div class="d-flex flex-center mt-3" style="height: 20px;">
                        <div class="flex-grow-1"></div>
                        <div class="bb" @click="cancel(); hide();">{{ $t('cancel') }}</div>
                        <div class="bb" @click="submit(); hide();">{{ $t('confirm') }}</div>
                    </div>
                </form>
            </template>
        </Dropdown>
    </div>
</template>

<style scoped></style>