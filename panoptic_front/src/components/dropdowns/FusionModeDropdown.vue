<script setup lang="ts">
import { useDataStore } from '@/data/dataStore';
import wTT from '@/components/tooltips/withToolTip.vue'
import Dropdown from './Dropdown.vue';

const data = useDataStore()

const props = defineProps<{
    modelValue: string
}>()
const emits = defineEmits(['update:modelValue'])
const modes = ['first', 'last', 'all', 'new']

</script>

<template>
    <Dropdown>
        <template #button>
            <div class="bbb">{{ $t('modals.import.fusion.' + props.modelValue) }}</div>
        </template>

        <template #popup="{hide}">
            <div class="p-1">
                <div v-for="mode in modes" @click="emits('update:modelValue', mode); hide();" class="bb m-1">
                    <span class="dropdown-item" style="cursor: pointer;">
                        <wTT :message="'modals.import.fusion.' + mode + '_tooltip'">
                            {{ $t('modals.import.fusion.' + mode) }}
                        </wTT>
                    </span>
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.main-box {
    width: 100px;
}
</style>