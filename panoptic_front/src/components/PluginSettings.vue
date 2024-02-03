<script setup lang="ts">
import { PluginDescription } from '@/data/models';
import { computed, reactive } from 'vue';

const props = defineProps<{
    plugin: PluginDescription
}>()

const actions = computed(() => {
    const res = {}
    props.plugin.registered_functions.forEach(f => {
        if (!res[f.action]) {
            res[f.action] = []
        }
        res[f.action].push(f)
    })
    return res
})

</script>

<template>
    <div>
        <h3 class="text-center">{{ props.plugin.name }}</h3>
        <div class="">{{ props.plugin.description }}</div>
        <div class="custom-hr mt-2 mb-2"></div>
        <h5>Registered Actions</h5>
        <div v-for="action in Object.keys(actions)">
            <div class="text-capitalize"><b>{{ action }}</b></div>
            <div v-for="func in actions[action]" class="function">
                <div>{{ func.name }}<span v-if="func.description" class="text-secondary">: {{ func.description }}</span></div>
                <template v-if="func.params.length">
                    <div class="custom-hr" style="margin: 2px 0;"></div>
                    <div v-for="param in func.params" class="param">
                        <div class="d-flex">
                            <div>{{ param.name }}</div>
                            <div class="ms-1">({{ param.type }})</div>
                            <div class="ms-1" style="margin-top: 3px;"><input type="number" placeholder="default-value" /></div>
                        </div>
                        <div class="text-secondary">{{ param.description }}</div>
                    </div>
                </template>

            </div>
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