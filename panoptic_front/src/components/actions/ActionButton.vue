<script setup lang="ts">
import { defineProps, defineEmits, ref, onMounted, watch, computed, nextTick } from 'vue';
import Dropdown from '../dropdowns/Dropdown.vue';
import { ActionContext, ExecuteActionPayload } from '@/data/models';
import { apiCallActions } from '@/data/api';
import { useProjectStore } from '@/data/projectStore';
import ParamInput from '../inputs/ParamInput.vue';
import ActionSelect from './ActionSelect.vue';

const project = useProjectStore()

const props = defineProps<{
    action: string
    imageIds?: number[]
    propertyIds?: number[]
}>()
const emits = defineEmits(['result'])

// const localAction = ref(null)
const localInputs = ref(null)
const inputElem = ref(null)

const defaultFunction = computed(() => project.actions.find(a => a.name == props.action).selectedFunction)
const localFunction = ref(null)


function loadAction() {
    localFunction.value = defaultFunction.value
    loadInput()
}

function loadInput() {
    const funcId = localFunction.value
    if (!funcId) return

    const pluginName = funcId.split('.')[0]
    const funcName = funcId.split('.')[1]
    const plugin = project.data.plugins.find(p => p.name == pluginName)
    const defaults = plugin.defaults.functions[funcName]
    const params = plugin.registeredFunctions.find(f => f.id == funcId).params

    const inputs = []
    for (let param of params) {
        inputs.push(Object.assign(param, { defaultValue: defaults[param.name] }))
    }
    localInputs.value = inputs
}

async function call() {
    const uiInputs = {}
    for (let input of localInputs.value) {
        uiInputs[input.name] = input.defaultValue
    }

    const context: ActionContext = { instanceIds: props.imageIds, propertyIds: props.propertyIds, uiInputs }
    const req: ExecuteActionPayload = { action: props.action, function: localFunction.value, context: context }
    const res = await apiCallActions(req)
    emits('result', res)
}

function setRef(elem, i) {
    if(i == 0 && elem) {
        elem.focus()
    }
}

onMounted(loadAction)
watch(() => props.action, loadAction)
watch(localFunction, loadInput)
watch(() => project.actions, loadAction)
</script>

<template>
    <div class="main d-flex" v-if="localFunction">
        <div @click="call">{{ $t('action.' + props.action) }}</div>
        <Dropdown :teleport="true">
            <template #button>
                <div class="sep base-hover"><i class="bi bi-chevron-down"></i></div>
            </template>
            <template #popup="{ hide }">
                <ActionSelect style="font-size: 10px; margin: 2px 2px 0 0;" class="text-end" v-model="localFunction"
                    :action="props.action" />
                <div class="p-2">
                    <form @submit.prevent="call(); hide();">
                        <div v-for="input, i in localInputs" class="mb-1">
                            <ParamInput :type="input.type" v-model="input.defaultValue" :label="input.name" :ref="r => setRef(r, i)" :desc="input.description" />
                        </div>
                        <div class="d-flex">
                            <div class="flex-grow-1"></div>
                            <div class="mt-1 base-btn text-center me-2 ps-1 pe-1" @click="hide">Cancel</div>
                            <div class="mt-1 base-btn text-center ps-1 pe-1" @click="call(); hide();">Call</div>
                        </div>
                    </form>
                </div>
            </template>
        </Dropdown>
    </div>
</template>

<style scoped>
.main {
    border: 2px solid var(--border-color);
    border-radius: 3px;
    padding: 1px 0px 1px 3px;
    cursor: pointer;
}

.sep {
    padding-left: 2px;
    padding-right: 2px;
    /* background-color: aqua; */
    /* border-left: 1px solid var(--border-color); */
}
</style>