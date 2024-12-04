<script setup lang="ts">
import { useActionStore } from '@/data/actionStore';
import { FunctionDescription } from '@/data/models';
import { objValues } from '@/utils/utils';
import { onMounted, computed, watch, reactive } from 'vue';

// const project = useProjectStore()
const actions = useActionStore()

const localDefaults = reactive({
    similar: undefined,
    group: undefined,
    execute: undefined,
    import: undefined,
    export: undefined
})

const availableActions = computed(() => {
    const res: { [action: string]: FunctionDescription[] } = {}
    Object.keys(localDefaults).forEach(k => res[k] = [])
    for(let action of objValues(actions.index)) {
        // console.log(action)
        for(let hook of action.hooks) {
            // console.log(hook, res[hook])
            if(res[hook] !== undefined) {
                res[hook].push(action)
            }
        }
    }
    return res
})

const changed = computed(() => {
    for (let k in localDefaults) {
        if (localDefaults[k] !== actions.defaultActions[k]) {
            return true
        }
    }
    return false
})

function updateLocal() {
    Object.assign(localDefaults, actions.defaultActions)
}

function applyChange() {
    actions.updateDefaultActions(localDefaults)
}

onMounted(updateLocal)
watch(() => actions.defaultActions, updateLocal)

</script>

<template>
    <div v-if="localDefaults" class="main">
        <h4 class="text-center">Actions</h4>
        <!-- <div class="custom-hr mb-3" /> -->
        <div>
            <div v-for="action in Object.keys(availableActions)" class="d-flex m-2">
                <div class="me-2" style="width: 120px;">{{ action }}</div>
                <select v-if="availableActions[action].length" v-model="localDefaults[action]">
                    <option v-for="func in availableActions[action]" :value="func.id">
                        {{ func.name }}
                    </option>
                </select>
                <div v-else class="text-secondary">None</div>
            </div>
        </div>

        <div v-if="changed" class="d-flex changed">
            <div class="flex-grow-1"></div>
            <div class="base-btn me-3" @click="updateLocal">Reset</div>
            <div class="base-btn" @click="applyChange">Update</div>
        </div>
    </div>
</template>

<style scoped>
.main {
    border: 1px solid var(--border-color);
    border-radius: 3px;
    /* padding: 5px; */
}

.changed {
    border-top: 1px solid var(--border-color);
    padding: 5px;
}
</style>