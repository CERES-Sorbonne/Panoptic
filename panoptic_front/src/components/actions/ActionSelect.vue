<script setup lang="ts">
import { useActionStore } from '@/data/actionStore';
import { ParamDescription } from '@/data/models';
import { objValues } from '@/utils/utils';
import { computed, onMounted, ref } from 'vue'
import Dropdown from '../dropdowns/Dropdown.vue';
import ParamInput from '../inputs/ParamInput.vue';
import wTT from '../tooltips/withToolTip.vue';

const actions = useActionStore()

const props = defineProps<{
    action: string
    hideGear?: boolean
    size?: number
}>()
const emits = defineEmits(['changed'])

const defaultFunction = computed(() => actions.defaultActions[props.action])

const localInputs = ref<ParamDescription[]>([])
const localFunction = ref(null)

const fontSize = computed(() => props.size ? props.size : 12)
const available = computed(() => {
    const valid = objValues(actions.index).filter(a => a.hooks.includes(props.action))
    return valid.map(a => a.id)
})

const sourceName = computed(() =>{
    return localFunction.value.slice(0, localFunction.value.indexOf('.'))
})


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

    for(let param of params) {
        param.defaultValue = defaults[param.name]
    }

    localInputs.value = JSON.parse(JSON.stringify(params))
}

async function submit() {
    const funcId = localFunction.value
    for (let i in localInputs.value) {
        actions.index[funcId].params[i].defaultValue = localInputs.value[i].defaultValue
    }
    await actions.updateDefaultParams()
    emits('changed')
}

function cancel() {
    loadInput()
}

async function updateFunction(func) {
    const update = {}
    update[props.action] = func
    await actions.updateDefaultActions(update)
    await loadAction()
    emits('changed')
}

onMounted(loadAction)

</script>

<template>
    <div class="d-flex" :style="{ fontSize: fontSize + 'px' }">
        <Dropdown>
            <template #button>
                <div>
                    <wTT class="p-0 m-0" v-if="localFunction" :message="actions.index[localFunction].description">
                        <span class="bbb">{{ localFunction }}<i class="ms-1 bi bi-chevron-down" /></span>
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
        <div v-if="localInputs.length && !props.hideGear" class="ms-1">
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
                            <ParamInput :input="input" :source="sourceName"/>
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
    </div>
</template>

<style scoped></style>