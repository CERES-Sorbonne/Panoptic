<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue';
import Dropdown from '../dropdowns/Dropdown.vue';
import { ActionContext, ExecuteActionPayload, Instance, ParamDescription } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import ParamInput from '../inputs/ParamInput.vue';
import ActionSelect from './ActionSelect.vue';
import { useActionStore } from '@/data/actionStore';
import { useDataStore } from '@/data/dataStore';
import wTT from '@/components/tooltips/withToolTip.vue'
import { usePanopticStore } from '@/data/panopticStore';
import { convertClusterGroupResult, sourceFromFunction } from '@/utils/utils';
import Autofocus from '../utils/Autofocus.vue';
import ActionSelect2 from './ActionSelect2.vue';

const project = useProjectStore()
const data = useDataStore()
const actions = useActionStore()
const panoptic = usePanopticStore()

const props = defineProps<{
    action: string
    images?: Instance[]
    propertyIds?: number[],
    autoCall?: boolean
}>()
const emits = defineEmits(['instances', 'groups'])

const localInputs = ref<ParamDescription[]>([])
const defaultFunction = computed(() => actions.defaultActions[props.action])
const localFunction = ref<string>(null)
const setDefault = ref(false)
const loading = ref(false)
const dropdownElem = ref(null)

const source = computed(() => sourceFromFunction(localFunction.value))

function loadAction() {
    localFunction.value = defaultFunction.value
    loadInput()
}

function loadInput() {
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

function handleMainClick() {
    if (props.autoCall) {
        call()
        return
    }

    dropdownElem.value.show()
}

onMounted(loadAction)
watch(() => actions.index, loadAction)
watch(defaultFunction, loadAction)
watch(() => props.action, loadAction)
watch(localFunction, loadInput)
</script>

<template>
    <Dropdown :teleport="true" @show="loadAction" ref="dropdownElem">
        <template #button>
            <div class="d-flex main2">
                <div v-if="loading" class="spinner-border spinner-border-sm text-primary me-1" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <wTT :message="'dropdown.action.' + props.action" class="">
                    <div class="">
                        <slot></slot>
                    </div>
                </wTT>
            </div>
        </template>
        <template #popup="{ hide }">
            <Autofocus @keydown.enter="call(); hide();">
                <div style="min-width: 200px; overflow: hidden;" class="d-flex flex-column">
                    <ActionSelect2 v-model="localFunction" :action="props.action" :hide-gear="true" :size="14" />
                    <div v-if="localInputs.length" style="padding-left: 5px; padding-right: 5px; margin-bottom: 3px;">
                        <form  @submit.prevent="" class="params-grid mt-1">
                            <template v-for="input, i in localInputs">
                                <ParamInput :input="input" :source="source" :max-width="200" />
                            </template>
                        </form>
                    </div>
                    <div class="d-flex flex-center p-1 bar" :class="{'no-shadow': localInputs.length == 0}">
                        <div class="me-1"><input type="checkbox" v-model="setDefault"
                                style="position: relative; top: 2px" /></div>
                        <div class="text-secondary" style="white-space: nowrap;">{{ $t('action.default')
                        }}
                        </div>
                        <div class="ms-2 flex-grow-1"></div>
                        <div class="bb" @click="hide">{{ $t('cancel') }}</div>
                        <div class="bb" @click="call(); hide();">{{ $t('call') }}</div>
                    </div>
                </div>
            </Autofocus>
        </template>
    </Dropdown>
</template>

<style scoped>
.main2 {
    cursor: pointer;
    /* padding: 0.5px; */
    font-size: 14px;
}

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
    -webkit-box-shadow: 0px 0px 2px 1px var(--border-color);
    box-shadow: 0px 0px 2px 1px var(--border-color);
}

.no-shadow {
    box-shadow: none !important;
    -webkit-box-shadow: none !important;
}
</style>