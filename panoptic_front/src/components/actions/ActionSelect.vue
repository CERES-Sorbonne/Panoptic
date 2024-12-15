<script setup lang="ts">
import { useActionStore } from '@/data/actionStore';
import { ActionContext, ParamDescription } from '@/data/models';
import { deepCopy, objValues } from '@/utils/utils';
import { computed, onMounted, ref, watch } from 'vue'
import Dropdown from '../dropdowns/Dropdown.vue';
import ParamInput from '../inputs/ParamInput.vue';

const actions = useActionStore()

const props = defineProps<{
    action: string
}>()
const emits = defineEmits(['changed'])

const defaultFunction = computed(() => actions.defaultActions[props.action])

const localInputs = ref<ParamDescription[]>([])
const localFunction = ref(null)

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
    <div class="d-flex">
        <Dropdown>
            <template #button>
                <span class="bbb">{{ localFunction }}<i style="font-size: 13px;" class="ms-1 bi bi-chevron-down" /></span>
            </template>
            <template #popup="{hide}">
                <div class="p-2">
                    <div v-for="f in available" class="bb" @click="updateFunction(f); hide();">{{ f }}</div>
                </div>
            </template>
        </Dropdown>
        <!-- <select :value="localFunction" @change="(e: any) => updateFunction(e.target.value)">
            <option v-for="f in available" :value="f">
                {{ f }}
            </option>
        </select> -->
        <div v-if="localInputs.length" class="ms-1">
            <Dropdown>
                <template #button>
                    <span class="bbb"><i class="bi bi-gear" /></span>
                </template>
                <template #popup="{ hide }">
                    <form @submit.prevent="submit(); hide();" class="p-2">
                        <div v-for="input, i in localInputs" class="mb-1">
                            <ParamInput :input="input" />
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