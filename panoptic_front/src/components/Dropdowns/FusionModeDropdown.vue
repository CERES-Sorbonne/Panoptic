<script setup lang="ts">
import { useDataStore } from '@/data/dataStore';
import wTT from '@/components/tooltips/withToolTip.vue'

const data = useDataStore()

const props = defineProps<{
    modelValue: string
}>()
const emits = defineEmits(['update:modelValue'])
const modes = ['first', 'last', 'all', 'new']

</script>

<template>
    <div class="dropdown">
        <button class="input-lg text-nowrap" type="button" data-bs-toggle="dropdown" aria-expanded="false">
            {{ $t('modals.import.fusion.' + props.modelValue) }}
        </button>

        <ul class="dropdown-menu">
            <li v-for="mode in modes" @click="emits('update:modelValue', mode)">
                <span class="dropdown-item" style="cursor: pointer;">
                    <wTT :message="'modals.import.fusion.' + mode + '_tooltip'" >
                        {{ $t('modals.import.fusion.' + mode) }}
                    </wTT>
                </span>
            </li>
        </ul>
        </div>
</template>

<style scoped>
.main-box {
    width: 100px;
}
</style>