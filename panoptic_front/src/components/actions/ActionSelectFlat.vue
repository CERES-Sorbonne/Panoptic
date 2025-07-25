<script setup lang="ts">
import { useActionStore } from '@/data/actionStore';
import { ActionContext, ExecuteActionPayload, ParamDescription } from '@/data/models';
import { deepCopy, objValues, sleep, sourceFromFunction } from '@/utils/utils';
import { computed, onMounted, ref } from 'vue'
import Dropdown from '../dropdowns/Dropdown.vue';
import wTT from '../tooltips/withToolTip.vue';
import ParamInputRow from '../inputs/ParamInputRow.vue';
import SectionDivider from '../utils/SectionDivider.vue';
import { useProjectStore } from '@/data/projectStore';
import { useDataStore } from '@/data/dataStore';

const actions = useActionStore()
const project = useProjectStore()
const data = useDataStore()

const props = defineProps<{
    action: string
    size?: number
}>()
const emits = defineEmits(['cancel', 'added'])


const options = ref(initOptions())


function initOptions() {
    return {
        autoCompute: true
    }
}

const loading = ref(false)

const defaultFunction = computed(() => actions.defaultActions[props.action])

const localInputs = ref<ParamDescription[]>([])
const localFunction = ref(null)

const fontSize = computed(() => props.size ? props.size : 12)
const available = computed(() => {
    const valid = objValues(actions.index).filter(a => a.hooks.includes(props.action))
    return valid.map(a => a.id)
})

function loadAction() {
    localFunction.value = defaultFunction.value
    loadInput()
}

function loadInput() {
    localInputs.value = []
    const funcId = localFunction.value
    if (!funcId) return

    if (!actions.index[funcId]) return
    const params = actions.index[funcId].params

    const defaults = actions.getContext(funcId).uiInputs

    for (let param of params) {
        param.defaultValue = defaults[param.name]
    }

    localInputs.value = JSON.parse(JSON.stringify(params))
}

async function call() {
    if (loading.value) return
    loading.value = true
    try {
        const uiInputs = {}
        for (let input of localInputs.value) {
            if (input.type == 'property' && !input.defaultValue && data.propertyList.length) {
                input.defaultValue = data.propertyList[0].id
            }
            uiInputs[input.name] = input.defaultValue
        }

        const context: ActionContext = { uiInputs }
        const req: ExecuteActionPayload = { function: localFunction.value, context: context }
        const res = await project.call(req)
        const vecType = res.value

        if (props.action == 'vector_type') {
            if (res && options.value.autoCompute) {
                await actions.callComputeVector(vecType)
            }
        }

    } catch (e) {
        console.error(e)
    }
    try {
        const funcId = localFunction.value
        for (let i in localInputs.value) {
            actions.index[funcId].params[i].defaultValue = localInputs.value[i].defaultValue
        }
        await actions.updateDefaultParams()

        const update = {}
        update[props.action] = localFunction.value
        await actions.updateDefaultActions(update)
    } catch (e) {

    }

    loading.value = false
    emits('added')
    cancel()
}

function confirmInput() {
    let inputs = deepCopy(localInputs.value)
}


function cancel() {
    loadInput()
    emits('cancel')
}

async function updateFunction(func) {
    const update = {}
    update[props.action] = func
    await actions.updateDefaultActions(update)
    await loadAction()
}

onMounted(loadAction)

</script>

<template>
    <div class="" :style="{ fontSize: fontSize + 'px' }">
        <table>
            <tbody>
                <tr style="height: 50px;">
                    <td>Function</td>
                    <td>
                        <Dropdown>
                            <template #button>
                                <div>
                                    <wTT class="p-0 m-0" v-if="localFunction"
                                        :message="actions.index[localFunction].description">
                                        <span class="bbb">{{ localFunction }}<i
                                                class="ms-1 bi bi-chevron-down" /></span>
                                    </wTT>
                                </div>
                            </template>
                            <template #popup="{ hide }">
                                <div class="p-2">
                                    <div v-for="f in available" class="bb" @click="updateFunction(f); hide();">
                                        <wTT :message="actions.index[f].description">
                                            {{ f }}
                                        </wTT>
                                    </div>
                                </div>
                            </template>
                        </Dropdown>
                    </td>
                </tr>
                <template v-if="localInputs.length">
                    <template v-for="input in localInputs">
                        <ParamInputRow :input="input" :source="sourceFromFunction(localFunction)" />
                    </template>
                </template>
                <template v-if="props.action == 'vector_type'">
                    <tr>
                        <td>
                            <wTT message="Dont check if you want to start compute manualy later">
                                <span class="me-1">Compute now</span>
                            </wTT>
                        </td>
                        <td>
                            <span>
                                <input type="checkbox" v-model="options.autoCompute" ref="elem" />
                            </span>
                        </td>
                    </tr>
                </template>
            </tbody>
        </table>
        <div class="ms-3 mt-3">
            <SectionDivider>
                <span class="bbb me-2" @click="cancel">Cancel</span>
                <span class="bbb" @click="call">Create</span>
                <div v-if="loading" class="ms-3 spinner-border spinner-border-sm text-primary me-1" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </SectionDivider>
        </div>
    </div>
</template>

<style scoped>
table {
    border-collapse: separate;
    border-spacing: 16px 0;
    /* Horizontal: 16px, Vertical: 0px */
}
</style>