<script setup lang="ts">
import { ActionDescription } from '@/data/models';
import { defineProps, defineEmits, ref, Ref, onMounted, computed, watch } from 'vue';

const props = defineProps<{
    actions: ActionDescription[]
}>()

const localActions = ref<ActionDescription[]>(null)

const changed = computed(() => {
    const index: {[key: string]: ActionDescription} = {}
    localActions.value.forEach(a => index[a.name] = a)
    for(let action of props.actions) {
        if(action.selectedFunction != index[action.name].selectedFunction) {
            return true
        }
    }
    return false
})

function updateLocal() {
    localActions.value = JSON.parse(JSON.stringify(props.actions))
}

function applyChange() {

}

onMounted(updateLocal)
watch(() => props.actions, updateLocal)

</script>

<template>
    <div v-if="localActions" class="ms-5 mt-5">
        <h4>Actions</h4>
        <div v-for="action in localActions" class="d-flex m-2">
            <div class="me-2">{{ action.name }}</div>
            <select v-if="action.availableFunctions.length" v-model="action.selectedFunction">
                <option v-for="func in action.availableFunctions" :value="func">
                    {{ func }}
                </option>
            </select>
            <div v-else class="text-secondary">None</div>
        </div>
        <div v-if="changed" class="d-flex">
            <!-- <div class="flex-grow-1"></div> -->
            <div class="base-btn me-3" @click="updateLocal">Reset</div>
            <div class="base-btn" @click="applyChange">Update</div>
        </div>
    </div>
</template>

<style scoped></style>