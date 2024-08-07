<script setup lang="ts">
import { defineProps, defineEmits, ref, onMounted, watch, computed } from 'vue';
import Dropdown from '../dropdowns/Dropdown.vue';
import { ActionContext, ExecuteActionPayload, Instance, ParamDescription } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import ParamInput from '../inputs/ParamInput.vue';
import ActionSelect from './ActionSelect.vue';
import { useActionStore } from '@/data/actionStore';
import { useDataStore } from '@/data/dataStore';
import wTT from '@/components/tooltips/withToolTip.vue'

const project = useProjectStore()
const data = useDataStore()
const actions = useActionStore()

const props = defineProps<{
    action: string
    images?: Instance[]
    propertyIds?: number[]
}>()
const emits = defineEmits(['instances', 'groups'])

const localInputs = ref<ParamDescription[]>([])
const defaultFunction = computed(() => actions.defaultActions[props.action])
const localFunction = ref(null)
const setDefault = ref(false)
const loading = ref(false)

function loadAction() {
    localFunction.value = defaultFunction.value
    loadInput()
}

function loadInput() {
    const funcId = localFunction.value
    if (!funcId) return

    if (!actions.index[funcId]) return
    const params = actions.index[funcId].params

    // const inputs = []
    // for (let param of params) {
    //     inputs.push(Object.assign(param, { defaultValue: defaults[param.name] }))
    // }
    localInputs.value = JSON.parse(JSON.stringify(params))
}

async function call() {
    if (loading.value) return
    loading.value = true
    try {
        console.log(localFunction.value, defaultFunction.value)
        const uiInputs = {}
        for (let input of localInputs.value) {
            if (input.type == 'property' && !input.defaultValue && data.propertyList.length) {
                input.defaultValue = data.propertyList[0].id
            }
            uiInputs[input.name] = input.defaultValue
        }
        const imageIds = props.images.map(i => i.id)
        const context: ActionContext = { instanceIds: imageIds, propertyIds: props.propertyIds, uiInputs }
        const req: ExecuteActionPayload = { function: localFunction.value, context: context }
        const res = await project.call(req)

        if (res.groups) {
            emits('groups', res.groups)
        }
        if (res.instances) {
            emits('instances', res.instances)
        }

        if (setDefault.value) {
            const funcId = localFunction.value
            for (let i in localInputs.value) {
                actions.index[funcId].params[i].defaultValue = localInputs.value[i].defaultValue
            }
            await actions.updateDefaultParams()

            const update = {}
            update[props.action] = localFunction.value
            await actions.updateDefaultActions(update)
        }
    } catch (e) {

    }
    loading.value = false
}

function setRef(elem, i) {
    if (i == 0 && elem) {
        elem.focus()
    }
}

onMounted(loadAction)
watch(defaultFunction, loadAction)
watch(() => props.action, loadAction)
watch(localFunction, loadInput)
watch(project.actions, loadAction)
</script>

<template>
    <div id="group-action-button" class="main d-flex flex-center" v-if="localFunction">
        <div v-if="loading" class="spinner-border spinner-border-sm text-primary me-1" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
        <wTT :message="'dropdown.action.' + props.action">
            <div @click="call">{{ $t('action.' + props.action) }}</div>
        </wTT>
        <div class="sep ms-1"></div>
        <Dropdown :teleport="true">
            <template #button>
                <div class="bb" style="margin: 0 1px; font-size: 8px;"><i class="bi bi-chevron-down"></i></div>
            </template>
            <template #popup="{ hide }">
                <div style="min-width: 200px;">
                    <ActionSelect style="font-size: 10px; margin: 2px 2px 0 0;" class="text-end" v-model="localFunction"
                        :action="props.action" />
                    <div class="p-2 pb-1">
                        <form @submit.prevent="call(); hide();" class="">
                            <div v-for="input, i in localInputs" class="mb-1">
                                <ParamInput :type="input.type" v-model="input.defaultValue" :label="input.name"
                                    :desc="input.description" />
                            </div>
                            <div class="d-flex flex-center mt-3" style="height: 20px;">
                                <div class="me-1"><input type="checkbox" v-model="setDefault"
                                        style="position: relative; top: 2px" /></div>
                                <div class="text-secondary">as default</div>
                                <div class="flex-grow-1"></div>
                                <div class="bb" @click="hide">Cancel</div>
                                <div class="bb" @click="call(); hide();">Call</div>
                            </div>
                        </form>
                    </div>
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
    height: 20px;
}

/* .sep {
    padding-left: 2px;
    padding-right: 2px;
} */
</style>