<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue';
import Dropdown from '../Dropdowns/Dropdown.vue';
import { ActionContext, ExecuteActionPayload, Instance, ParamDescription } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import ParamInput from '../inputs/ParamInput.vue';
import ActionSelect from './ActionSelect.vue';
import { useActionStore } from '@/data/actionStore';
import { useDataStore } from '@/data/dataStore';
import wTT from '@/components/tooltips/withToolTip.vue'
import { usePanopticStore } from '@/data/panopticStore';
import { convertClusterGroupResult } from '@/utils/utils';
import Autofocus from '../utils/Autofocus.vue';

const project = useProjectStore()
const data = useDataStore()
const actions = useActionStore()
const panoptic = usePanopticStore()

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
        const imageIds = props.images.map(i => i.id)
        const context: ActionContext = { instanceIds: imageIds, propertyIds: props.propertyIds, uiInputs }
        const req: ExecuteActionPayload = { function: localFunction.value, context: context }
        const res = await project.call(req)

        if (res.groups) {
            const groups = convertClusterGroupResult(res.groups, context)
            emits('groups', groups)
        }
    } catch (e) {
        console.error(e)
    }
    try {
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

onMounted(loadAction)
watch(() => actions.update, loadAction)
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
                <Autofocus @keydown.enter="call(); hide();">
                    <div style="min-width: 200px;" class="p-1">
                        <div class="">
                            <ActionSelect v-model="localFunction" :action="props.action" :hide-gear="true" :size="12" />
                        </div>
                        <div class="ps-1 pt-1 pb-1">
                            <form @submit.prevent="" class="">
                                <div v-for="input, i in localInputs" class="mb-1">
                                    <ParamInput :input="input" />
                                </div>
                                <div class="d-flex flex-center mt-3 pe-1" style="height: 20px;">
                                    <div class="me-1"><input type="checkbox" v-model="setDefault"
                                            style="position: relative; top: 2px" /></div>
                                    <div class="text-secondary" style="white-space: nowrap;">{{ $t('action.default') }}
                                    </div>
                                    <div class="ms-2 flex-grow-1"></div>
                                    <div class="bb" @click="hide">{{ $t('cancel') }}</div>
                                    <div class="bb" @click="call(); hide();">{{ $t('call') }}</div>
                                </div>
                            </form>
                        </div>
                    </div>
                </Autofocus>
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