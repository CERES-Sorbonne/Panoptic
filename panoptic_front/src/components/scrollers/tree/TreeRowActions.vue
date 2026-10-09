<script setup lang="ts">
// The buttons a tree/cluster property row shows on hover: filter the tab on the row's value,
// copy the row's full value. Shared by TreeCellFrame (editor rows, cluster cards) and
// TreeCellView (the tree's read-only rows); both mount it only while the row is pointed at.
//
// Its root is `.row-actions`, styled (placed, and shown on the row's :hover) by the row itself.
import wTT from '@/components/tooltips/withToolTip.vue'
import { PropertyType } from '@/data/models'
import { Filter, FilterGroup, FilterOperator } from '@/core/FilterManager'
import { computed, onUnmounted, ref } from 'vue'
import { useTabStore } from '@/data/stores/tabStore'

const props = defineProps<{
    type: PropertyType
    // The row's property and raw value, for the filter button. Without it there is no filter
    // button (the cluster cards edit a group's value, not one image's).
    filter?: { propertyId: number, value: any }
    // The row's full value, for the copy button: the same text its tooltip would show.
    text: () => string | undefined
}>()

const tabStore = useTabStore()
const filterManager = () => tabStore.getMainTab().collection.filterManager

// every filter of the tab on this row's property, nested groups included
function propertyFilters(): Filter[] {
    const propertyId = props.filter.propertyId
    const found: Filter[] = []
    const visit = (group: FilterGroup) => group.filters.forEach(f => {
        if (f.isGroup) visit(f as FilterGroup)
        else if ((f as Filter).propertyId == propertyId) found.push(f as Filter)
    })
    visit(filterManager().state.filter)
    return found
}

// Filled blue, as in the property panel, while any filter of the tab is on this property
const isFiltered = computed(() => !!props.filter && propertyFilters().length > 0)

// Toggles "property = this value" ("contains" for tags) on the current tab's filters. A second
// click removes the property's filters, matching the blue state above.
function filterValue() {
    const manager = filterManager()
    const existing = propertyFilters()
    if (existing.length) {
        existing.forEach(f => manager.deleteFilter(f.id))
        return
    }
    const { propertyId, value } = props.filter
    const filter = manager.addNewFilter(propertyId)
    // tag properties have no "equal": match images that have all of the row's tags
    // (a single-tag property only offers "any", which is the same thing for one tag)
    const operator = props.type == PropertyType.multi_tags ? FilterOperator.containsAll
        : props.type == PropertyType.tag ? FilterOperator.containsAny
        : FilterOperator.equal
    manager.updateFilter(filter.id, { operator, value })
}

const copied = ref(false)
let copiedTimer: ReturnType<typeof setTimeout>

async function copyValue() {
    const text = props.text()
    if (!text) return
    await navigator.clipboard.writeText(text)
    copied.value = true
    clearTimeout(copiedTimer)
    copiedTimer = setTimeout(() => copied.value = false, 1000)
}

onUnmounted(() => clearTimeout(copiedTimer))
</script>

<template>
    <!-- mousedown.prevent keeps an open editor focused; click.stop keeps the row from opening one -->
    <span class="row-actions">
        <!-- the styled span sits inside wTT: scoped styles can't reach wTT's own trigger span -->
        <wTT v-if="props.filter" message=".filter_by_value" :click="false">
            <span class="row-btn" @mousedown.prevent @click.stop="filterValue">
                <i :class="isFiltered ? 'bi bi-funnel-fill text-primary' : 'bi bi-funnel'" />
            </span>
        </wTT>
        <wTT message=".copy" :click="false">
            <span class="row-btn" @mousedown.prevent @click.stop="copyValue">
                <i :class="copied ? 'bi bi-check2' : 'bi bi-copy'" />
            </span>
        </wTT>
    </span>
</template>

<style scoped>
.row-btn {
    padding: 0 3px;
    font-size: 12px;
    line-height: 18px;
    color: var(--grey-text);
}

.row-btn:hover {
    color: black;
}
</style>
