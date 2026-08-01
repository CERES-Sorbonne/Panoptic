<script setup lang="ts">
import PropertyInputTable from '@/components/inputs/PropertyInputTable.vue';
import { useDataStore } from '@/data/dataStore';
import { useModalStore } from '@/data/modalStore';
import { deletedID, isReadonly, ModalId, PropertyMode } from '@/data/models';
import { InstanceEntry } from '@/data/instanceStore';
import { computed, reactive } from 'vue';

const data = useDataStore()
const modals = useModalStore()

const props = defineProps<{
    instance: InstanceEntry
    visibleProperties: { [id: number]: boolean }
}>()

const emits = defineEmits<{
    paint: [e: { instanceId: number, propertyId: number }]
    hover
    hoverEnd
}>()

const closed = reactive({})

const imageProperties = computed(() => data.propertyList.filter(p => p.mode == PropertyMode.sha1 && !isReadonly(p) && p.id != deletedID))
const instanceProperties = computed(() => data.propertyList.filter(p => p.mode == PropertyMode.id && !isReadonly(p) && p.id != deletedID))
const metaProperties = computed(() => data.propertyList.filter(p => (p.id < 0 || isReadonly(p)) && p.id != deletedID))

function toggleClosed(index: number) {
    if (closed[index]) {
        delete closed[index]
        return
    }
    closed[index] = true
}
</script>

<template>
    <div class="h-100" style="overflow-y: auto;">
        <div class="option" @click="toggleClosed(0)">
            <span>
                <i v-if="closed[0]" class="bi bi-caret-right-fill" />
                <i v-else class="bi bi-caret-down-fill"></i>
            </span>
            {{ $t('common.properties.image') }}
        </div>
        <template v-if="!closed[0]">
            <PropertyInputTable :image="props.instance" :properties="imageProperties"
                :visible-properties="visibleProperties" @paint="e => emits('paint', e)" @hover="emits('hover')"
                @hoverEnd="emits('hoverEnd')" />
            <div @click="modals.openModal(ModalId.PROPERTY, { mode: PropertyMode.sha1 })"
                class="btn-icon base-hover text-secondary" style="line-height: 25px;">
                <i class="bi bi-plus btn-icon" style="font-size: 25px;"></i>
                <span>{{ $t('main.nav.properties.add_property') }}</span>
            </div>
        </template>
        <div class="option" @click="toggleClosed(1)">
            <span>
                <i v-if="closed[1]" class="bi bi-caret-right-fill" />
                <i v-else class="bi bi-caret-down-fill"></i>
            </span>
            {{ $t('common.properties.instance') }}
        </div>
        <template v-if="!closed[1]">
            <PropertyInputTable :image="props.instance" :properties="instanceProperties"
                :visible-properties="visibleProperties" @paint="e => emits('paint', e)" @hover="emits('hover')"
                @hoverEnd="emits('hoverEnd')" />
            <div @click="modals.openModal(ModalId.PROPERTY, { mode: PropertyMode.id })"
                class="btn-icon base-hover text-secondary" style="line-height: 25px;">
                <i class="bi bi-plus btn-icon" style="font-size: 25px;"></i>
                <span>{{ $t('main.nav.properties.add_property') }}</span>
            </div>
        </template>
        <div class="option" @click="toggleClosed(2)">
            <span>
                <i v-if="closed[2]" class="bi bi-caret-right-fill" />
                <i v-else class="bi bi-caret-down-fill"></i>
            </span>
            {{ $t('common.properties.metadata') }}
        </div>
        <PropertyInputTable v-if="!closed[2]" :image="props.instance" :properties="metaProperties"
            :visible-properties="visibleProperties" @paint="e => emits('paint', e)" @hover="emits('hover')"
            @hoverEnd="emits('hoverEnd')" />
    </div>
</template>

<style scoped>
.option {
    font-size: 14px;
    line-height: 26px;
    background-color: var(--tab-grey);
    border-bottom: 1px solid var(--border-color);
    cursor: pointer;
}
</style>
