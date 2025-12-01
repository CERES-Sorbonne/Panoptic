<script setup lang="ts">
import { useActionStore } from '@/data/actionStore';
import { ParamDescription } from '@/data/models';
import { objValues } from '@/utils/utils';
import { computed, onMounted, ref } from 'vue'
import Dropdown from '../dropdowns/Dropdown.vue';
import wTT from '../tooltips/withToolTip.vue';

const actions = useActionStore()

const props = defineProps<{
    action: string
    size?: number
}>()
const emits = defineEmits(['changed'])

const defaultFunction = computed(() => actions.defaultActions[props.action])

const localInputs = ref<ParamDescription[]>([])
const localFunction = ref<string>(null)

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



async function updateFunction(func, hide) {
    const update = {}
    update[props.action] = func
    hide()
    await actions.updateDefaultActions(update)
    await loadAction()
    emits('changed')

}

onMounted(loadAction)

</script>

<template>
    <div class="" :style="{ fontSize: fontSize + 'px' }">
        <Dropdown placement="bottom-start">
            <template #button>
                <div class="b-box">
                    <wTT class="p-0 m-0" v-if="localFunction" :message="actions.index[localFunction].description">
                        <span>{{ localFunction }}</span>
                    </wTT>
                    <div class="flex-grow-1"></div>
                    <i class="ms-1 bi bi-chevron-down" />
                </div>
            </template>
            <template #popup="{ hide }">
                <div v-for="func in available" :class="['bb', { 'is-selected': func === localFunction }]"
                    @click="updateFunction(func, hide)">
                    <wTT :message="actions.index[func].description">
                        {{ actions.index[func].id }}
                    </wTT>
                </div>

                <div v-if="available.length === 0" class="text-gray-500 p-2 text-sm">
                    No options available
                </div>
            </template>
        </Dropdown>
    </div>
</template>

<style scoped>
.b-box {
    display: flex;
    padding: 4px 8px;
    -webkit-box-shadow: 0px 0px 2px 1px var(--border-color);
    box-shadow: 0px 0px 2px 1px var(--border-color);
    /* background-color: var(--border-color); */
    cursor: pointer;
}

.is-selected {
    background-color: var(--grey);
}
</style>