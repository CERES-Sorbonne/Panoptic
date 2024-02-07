<script setup lang="ts">
import { FunctionDescription, PluginDefaultParams, PluginDescription } from '@/data/models';
import { computed, onMounted, ref, watch } from 'vue';
import ParamInput from './inputs/ParamInput.vue';
import { useProjectStore } from '@/data/projectStore';

const project = useProjectStore()

const props = defineProps<{
    plugin: PluginDescription
}>()

const localDefaults = ref(null as PluginDefaultParams)

const defaultsChanged = computed(() => {
    if (!localDefaults.value) return false
    for (let func in props.plugin.defaults.functions) {
        for (let param in props.plugin.defaults.functions[func]) {
            if (props.plugin.defaults.functions[func][param] != localDefaults.value.functions[func][param]) {
                return true
            }
        }
    }
    for (let param in props.plugin.defaults.base) {
        if(props.plugin.defaults.base[param] != localDefaults.value.base[param]) {
            return true
        }
    }
    return false
})
const actions = computed(() => {
    const res: { [key: string]: FunctionDescription[] } = {}
    props.plugin.registeredFunctions.forEach(f => {
        if (!res[f.action]) {
            res[f.action] = []
        }
        const functionCopy: FunctionDescription = JSON.parse(JSON.stringify(f))
        res[f.action].push(functionCopy)
    })
    return res
})



function updateLocalDefaults() {
    localDefaults.value = JSON.parse(JSON.stringify(props.plugin.defaults))
}

function applyLocalDefaults() {
    project.setPluginDefaults(localDefaults.value)
}

onMounted(updateLocalDefaults)
watch(() => props.plugin, updateLocalDefaults)
// watch(actions, () => console.log('lala'))

</script>

<template>
    <div v-if="localDefaults">
        <h3 class="text-center">{{ props.plugin.name }}</h3>
        <div class="">{{ props.plugin.description }}</div>
        <div class="custom-hr mt-2 mb-2"></div>
        <h5>Base Settings</h5>
        <div class="function">
            <div v-for="param in props.plugin.baseParams.params" class="param">
                <ParamInput :type="param.type" v-model="localDefaults.base[param.name]" :label="param.name" />
                <div class="text-secondary">{{ param.description }}</div>
            </div>
        </div>
        <h5>Registered Actions</h5>
        <div v-for="action in Object.keys(actions)">
            <div class="text-capitalize"><b>{{ action }}</b></div>
            <div v-for="func in actions[action]" class="function">
                <div>{{ func.name }}<span v-if="func.description" class="text-secondary">: {{ func.description }}</span>
                </div>
                <template v-if="func.params.length">
                    <div class="custom-hr" style="margin: 2px 0;"></div>
                    <div v-for="param in func.params" class="param">
                        <!-- <div class="d-flex"> -->
                        <!-- <div class="ms-1" style="margin-top: 3px;"><input type="number" placeholder="default-value" /></div> -->
                        <ParamInput :type="param.type" v-model="localDefaults.functions[func.name][param.name]"
                            :label="param.name" />
                        <!-- </div> -->
                        <div class="text-secondary">{{ param.description }}</div>
                    </div>
                </template>
            </div>
        </div>
        <div v-if="defaultsChanged" class="d-flex">
            <div class="flex-grow-1"></div>
            <div class="base-btn me-3" @click="updateLocalDefaults">Reset</div>
            <div class="base-btn" @click="applyLocalDefaults">Update</div>
        </div>
    </div>
</template>

<style scoped>
.function {
    background-color: rgb(244, 244, 244);
    margin-left: 10px;
    padding: 2px 5px;
    border-radius: 5px;
    margin-bottom: 4px;
}

.param {
    background-color: rgb(255, 255, 255);
    padding: 4px;
    margin: 4px;
    border-radius: 5px;
}
</style>