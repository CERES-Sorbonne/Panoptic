<script setup lang="ts">
// "Assign to…": what a card's input row (and the inspector header) shows while the view has no
// grouping, so no target property. Picking a property P makes it the target: the view groups by
// P, the piles move into P's "no value" group with the same ids, and the ordinary typed input
// takes this control's place. "New property…" goes through the app's own creation modal first.
// Only the choice is made here — the grouping and the modal belong to GroupView, which outlives a
// card recycled out of the virtualized list.
import { computed } from 'vue'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
import PropertySelection from '@/components/inputs/PropertySelection.vue'
import { isReadonly, PropertyType } from '@/data/models'
import { useDataStore } from '@/data/stores/dataStore'

const data = useDataStore()

const emits = defineEmits<{
    choose: [propertyId: number]
    create: []
}>()

// Properties a pile can be assigned on: writable, and with a "no value" group for the piles to
// move into. A checkbox has none (unset reads as false), so choosing one would drop the piles.
const ASSIGNABLE = [
    PropertyType.tag, PropertyType.multi_tags, PropertyType.string, PropertyType.number,
    PropertyType.date, PropertyType.color, PropertyType.url,
]
const readonlyIds = computed(() => data.propertyList.filter(p => isReadonly(p)).map(p => p.id))
</script>

<template>
    <Dropdown :teleport="true" placement="bottom-start" :auto-focus="false">
        <template #button>
            <!-- No @click.stop here: floating-vue opens on a click reaching its own wrapper
                 around this slot. The row around the control already stops it at the card. -->
            <div class="assign-target">
                <i class="bi bi-tag me-1" />
                <span class="assign-label">{{ $t('main.group.assign_to') }}</span>
            </div>
        </template>
        <template #popup="{ hide }">
            <div class="assign-popup" @click.stop>
                <PropertySelection :acceptable-types="ASSIGNABLE" :ignore-ids="readonlyIds"
                    @select="id => { hide(); emits('choose', id) }" />
                <div class="assign-new base-hover" @click="hide(); emits('create')">
                    <i class="bi bi-plus me-1" />{{ $t('main.group.new_property') }}
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
/* Same box as the typed input it stands in for: the full row, 26px high, so a card keeps its
   height whether or not a target is chosen. */
.assign-target {
    display: flex;
    align-items: center;
    height: 26px;
    padding: 0 6px;
    font-size: 12px;
    color: var(--text-secondary);
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
}

.assign-target:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.assign-label {
    overflow: hidden;
    text-overflow: ellipsis;
}

.assign-popup {
    min-width: 200px;
}

.assign-new {
    display: flex;
    align-items: center;
    height: 26px;
    margin: 0 4px 4px;
    padding: 0 var(--spacing-xs);
    border-top: 1px solid var(--border-color);
    cursor: pointer;
    white-space: nowrap;
}
</style>
