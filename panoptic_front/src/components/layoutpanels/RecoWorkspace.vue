<script setup lang="ts">
// Group recommendation workspace. Header: view title, then the group selection
// and the similarity function. Below: a top-level vertical split between the
// next-recommendation hero (accept / refuse) and the panels block. The panels
// block holds three panels — the incoming queue, the images already in the
// group, and the blacklist — each a virtualized TreeScroller backed by its own
// standalone GroupManager. The hero divider resizes the hero against the whole
// panels block; the panels resize among themselves and can be collapsed to their
// header. (Selection is global for now; a per-panel namespace comes later.)
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import CenteredImage from '@/components/images/CenteredImage.vue'
import PropertyValue from '@/components/properties/PropertyValue.vue'
import ActionSelect from '@/components/actions/ActionSelect.vue'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
import wTT from '@/components/tooltips/withToolTip.vue'
import RecoPanel from '@/components/layoutpanels/RecoPanel.vue'
import { Group, GroupManager, GroupType } from '@/core/GroupManager'
import { CollectionManager } from '@/core/CollectionManager'
import { TabManager } from '@/core/TabManager'
import {
    ImagePropertyValue, Instance, InstancePropertyValue,
    PropertyMode, PropertyType, PropertyValue as PropertyValueModel, RecoOptions,
} from '@/data/models'
import { useActionStore } from '@/data/actionStore'
import { useDataStore } from '@/data/dataStore'
import { useColumnStore } from '@/data/columnStore'
import { convertSearchGroupResult, getGroupParents, sortGroupByScore } from '@/utils/utils'
import { apiGetUIData, apiSetUIData } from '@/data/apiProjectRoutes'

const data = useDataStore()
const actions = useActionStore()
const col = useColumnStore()

const props = defineProps<{
    tab: TabManager
    collection: CollectionManager
    recoOptions: RecoOptions
    imageSize: number
    width: number
    height: number
}>()

// ---- Group selection ---------------------------------------------------------

function isEligible(g: Group): boolean {
    const hasImages = g.slots.length > 0
    const hasSubgroups = g.children.length > 0 && g.subGroupType != GroupType.Sha1
    const someValue = (g.meta.propertyValues ?? []).some(v => v.value != undefined)
    return hasImages && !hasSubgroups && g.type != GroupType.Cluster && someValue
}

// Eligible leaf groups in display order (DFS).
const eligibleGroups = computed(() => {
    props.collection.groupManager.version.value // reactive dep on the group tree
    const root = props.collection.groupManager.result?.root
    if (!root) return [] as Group[]
    const res: Group[] = []
    const stack: Group[] = [root]
    while (stack.length) {
        const g = stack.pop()!
        if (isEligible(g)) res.push(g)
        for (let i = g.children.length - 1; i >= 0; i--) stack.push(g.children[i])
    }
    return res
})

// Selected group, revalidated against the eligible list (falls back to first).
const group = computed<Group | null>(() => {
    const groups = eligibleGroups.value
    if (!groups.length) return null
    return groups.find(g => g.id === props.recoOptions.selectedGroupId) ?? groups[0]
})

function groupLabel(g: Group) {
    const values: PropertyValueModel[] = []
    getGroupParents(g).reverse().forEach(p => values.push(...(p.meta.propertyValues ?? [])))
    values.push(...(g.meta.propertyValues ?? []))
    return values
}

function selectGroup(g: Group) {
    props.recoOptions.selectedGroupId = g.id
}

// ---- Search + curation state -------------------------------------------------

const searchResult = ref<Group>(null)
const propertyValues = reactive([]) as PropertyValueModel[]
const blacklist = reactive(new Set<number>())
const useFilter = ref(true)

const similarIds = ref<number[]>([])

const groupIds = computed<number[]>(() => {
    props.collection.groupManager.version.value
    if (!group.value) return []
    const ids = col.instanceIds()
    const g = props.collection.groupManager.result.index[group.value.id]
    return g ? g.slots.map(s => ids[s]) : []
})

const queueIds = computed<number[]>(() => {
    const inGroup = new Set(groupIds.value)
    return similarIds.value.filter(id => !inGroup.has(id) && !blacklist.has(id))
})

const blacklistIds = computed<number[]>(() => Array.from(blacklist))

const hero = computed<Instance | null>(() => {
    const id = queueIds.value[0]
    return id != undefined ? data.instances[id] : null
})

// ---- Standalone GroupManagers feeding the three panels -----------------------

const queueManager = new GroupManager()
const groupManager = new GroupManager()
const blacklistManager = new GroupManager()

const queueReady = ref(false)
const groupReady = ref(false)
const blacklistReady = ref(false)

function idsToSlots(ids: number[]): Int32Array {
    const slots: number[] = []
    for (const id of ids) {
        const s = col.slotMap.get(id)
        if (s !== undefined) slots.push(s)
    }
    return new Int32Array(slots)
}

async function rebuild(manager: GroupManager, ids: number[], ready: { value: boolean }) {
    await manager.group(idsToSlots(ids), true)
    ready.value = true
}

watch(queueIds, ids => rebuild(queueManager, ids, queueReady), { immediate: true })
watch(groupIds, ids => rebuild(groupManager, ids, groupReady), { immediate: true })
watch(blacklistIds, ids => rebuild(blacklistManager, ids, blacklistReady), { immediate: true })

// ---- Blacklist persistence (one entry per group id) --------------------------

function blacklistKey() {
    return 'group_blacklist.' + group.value?.id
}

async function loadBlacklist() {
    blacklist.clear()
    if (!group.value) return
    const saved = await apiGetUIData(blacklistKey()) as number[] | null
    if (Array.isArray(saved)) saved.forEach(id => blacklist.add(id))
}

function persistBlacklist() {
    if (!group.value) return
    apiSetUIData(blacklistKey(), Array.from(blacklist)) // fire-and-forget
}

// ---- Recommendations ---------------------------------------------------------

async function getReco() {
    similarIds.value = []
    if (!group.value) return
    if (!actions.hasSimilaryFunction) return

    const func = actions.defaultActions['similar']
    const ctx = actions.getContext(func)
    const ids = col.instanceIds()
    ctx.instanceIds = group.value.slots.map(s => ids[s])

    const res = await actions.getSimilarImages(ctx)
    if (!res || !res.groups) return

    let searchGroup = convertSearchGroupResult(res.groups)[0]
    if (!searchGroup) return

    if (useFilter.value) {
        const valid = new Set(
            Array.from(props.collection.filterManager.result.slots).map(s => ids[s])
        )
        searchGroup.slots = searchGroup.slots.filter(s => valid.has(ids[s]))
    }
    if (searchGroup.scores) sortGroupByScore(searchGroup)
    searchResult.value = searchGroup

    // The group's defining property values (walked up the tree) — applied on accept.
    propertyValues.length = 0
    let current: Group = group.value
    while (current) {
        if (current.meta.propertyValues) propertyValues.push(...current.meta.propertyValues)
        current = current.parent
    }

    await loadBlacklist()
    similarIds.value = searchGroup.slots.map(s => ids[s])
}

async function acceptRecommend(image: Instance) {
    const imageValues: ImagePropertyValue[] = []
    const instanceValues: InstancePropertyValue[] = []

    propertyValues.forEach(v => {
        if (v.value != undefined) {
            const prop = data.properties[v.propertyId]
            let value = v.value
            if (prop.type == PropertyType.multi_tags) {
                value = image.properties[v.propertyId] ?? []
                value = [...value, v.value]
            } else if (prop.type == PropertyType.tag) {
                value = [value]
            }
            if (prop.mode == PropertyMode.id) {
                instanceValues.push({ instanceId: image.id, propertyId: prop.id, value })
            } else {
                imageValues.push({ propertyId: prop.id, sha1: image.sha1, value })
            }
        }
    })
    await data.setPropertyValues(instanceValues, imageValues)
    // The image now matches the group; also blacklist it so it isn't re-proposed.
    refuseRecommend(image)
}

function refuseRecommend(image: Instance) {
    if (searchResult.value?.isSha1Group) {
        const ids = col.instanceIds()
        searchResult.value.slots
            .map(s => data.instances[ids[s]])
            .filter(img => img?.sha1 == image.sha1)
            .forEach(img => blacklist.add(img.id))
    } else {
        blacklist.add(image.id)
    }
    persistBlacklist()
}

function toggleFilter() {
    useFilter.value = !useFilter.value
}

onMounted(getReco)
watch(group, getReco)
watch(useFilter, getReco)

// ---- Resizable / collapsible stack -------------------------------------------

const HEADER_PX = 27  // a collapsed panel keeps only its header

type PanelKey = 'queue' | 'group' | 'blacklist'
const panelKeys: PanelKey[] = ['queue', 'group', 'blacklist']

// Top-level split: the hero vs the whole panels block.
const heroWeight = ref(1.3)
const panelsWeight = ref(2.7)

// Weights + collapse state within the panels block.
const panelWeights = reactive<Record<PanelKey, number>>({ queue: 1, group: 1, blacklist: 1 })
const collapsed = reactive<Record<PanelKey, boolean>>({ queue: false, group: false, blacklist: false })

const panelItems = computed(() => ([
    { key: 'queue' as PanelKey, titleKey: 'main.reco.incoming', count: queueIds.value.length, manager: queueManager, ready: queueReady.value, inputKey: 'reco-queue', emptyKey: 'main.reco.no_more' },
    { key: 'group' as PanelKey, titleKey: 'main.reco.in_group', count: groupIds.value.length, manager: groupManager, ready: groupReady.value, inputKey: 'reco-group', emptyKey: '' },
    { key: 'blacklist' as PanelKey, titleKey: 'main.reco.blacklist', count: blacklistIds.value.length, manager: blacklistManager, ready: blacklistReady.value, inputKey: 'reco-blacklist', emptyKey: '' },
]))

const heroStyle = computed(() => ({ flex: `${heroWeight.value} 1 0`, minHeight: '150px' }))
const panelsStyle = computed(() => ({ flex: `${panelsWeight.value} 1 0`, minHeight: '0' }))

function panelSlotStyle(key: PanelKey) {
    if (collapsed[key]) return { flex: '0 0 auto' }
    return { flex: `${panelWeights[key]} 1 0`, minHeight: '0' }
}

function toggleCollapse(key: PanelKey) {
    collapsed[key] = !collapsed[key]
}

// Nearest expanded panel strictly after position li (the handle sits after li).
function nextExpandedPanel(li: number): number {
    for (let j = li + 1; j < panelKeys.length; j++) if (!collapsed[panelKeys[j]]) return j
    return -1
}

// Nearest expanded panel at or before position li — the collapsed panels between
// it and the handle are skipped so the divider still resizes across them.
function prevExpandedPanel(li: number): number {
    for (let j = li; j >= 0; j--) if (!collapsed[panelKeys[j]]) return j
    return -1
}

function showPanelHandle(li: number): boolean {
    return prevExpandedPanel(li) !== -1 && nextExpandedPanel(li) !== -1
}

const stackRef = ref<HTMLElement>()
const panelsRef = ref<HTMLElement>()

type ResizeState =
    | { mode: 'hero'; startY: number; wh: number; wp: number }
    | { mode: 'panel'; a: PanelKey; b: PanelKey; startY: number; wa: number; wb: number }
let resizeState: ResizeState | null = null

function startHeroResize(e: PointerEvent) {
    resizeState = { mode: 'hero', startY: e.clientY, wh: heroWeight.value, wp: panelsWeight.value }
    attachResize()
    e.preventDefault()
}

function startPanelResize(li: number, e: PointerEvent) {
    const i = prevExpandedPanel(li)
    const j = nextExpandedPanel(li)
    if (i < 0 || j < 0) return
    resizeState = {
        mode: 'panel', a: panelKeys[i], b: panelKeys[j], startY: e.clientY,
        wa: panelWeights[panelKeys[i]], wb: panelWeights[panelKeys[j]],
    }
    attachResize()
    e.preventDefault()
}

function attachResize() {
    window.addEventListener('pointermove', onResize)
    window.addEventListener('pointerup', stopResize)
}

function onResize(e: PointerEvent) {
    if (!resizeState) return
    if (resizeState.mode === 'hero') {
        const { startY, wh, wp } = resizeState
        const total = wh + wp
        const px = stackRef.value?.clientHeight ?? 0
        if (px <= 0) return
        const dw = ((e.clientY - startY) / px) * total
        const min = 0.4
        const na = Math.min(total - min, Math.max(min, wh + dw))
        heroWeight.value = na
        panelsWeight.value = total - na
    } else {
        const { a, b, startY, wa, wb } = resizeState
        const total = wa + wb
        const sumW = panelKeys.filter(k => !collapsed[k]).reduce((s, k) => s + panelWeights[k], 0)
        const collapsedCount = panelKeys.filter(k => collapsed[k]).length
        const px = (panelsRef.value?.clientHeight ?? 0) - collapsedCount * HEADER_PX
        if (px <= 0 || sumW <= 0) return
        const combinedPx = px * total / sumW
        const dw = ((e.clientY - startY) / combinedPx) * total
        const min = 0.15
        const na = Math.min(total - min, Math.max(min, wa + dw))
        panelWeights[a] = na
        panelWeights[b] = total - na
    }
}

function stopResize() {
    resizeState = null
    window.removeEventListener('pointermove', onResize)
    window.removeEventListener('pointerup', stopResize)
}

onBeforeUnmount(stopResize)

// ---- Hero image sizing (tracks its resizable slot) ---------------------------

const heroImageRef = ref<HTMLElement>()
const heroDims = ref({ width: 0, height: 0 })
let heroObserver: ResizeObserver | null = null

watch(heroImageRef, (el, old) => {
    if (!heroObserver) {
        heroObserver = new ResizeObserver(entries => {
            for (const entry of entries) {
                const { width, height } = entry.contentRect
                heroDims.value = { width, height }
            }
        })
    }
    if (old) heroObserver.unobserve(old)
    if (el) heroObserver.observe(el)
})

onBeforeUnmount(() => heroObserver?.disconnect())
</script>

<template>
    <div class="reco-workspace" :style="{ height: props.height + 'px' }">
        <!-- Header: title, then group selection + similarity function -->
        <div class="reco-header">
            <div class="reco-title">{{ $t('main.recommand.title') }}</div>
            <div class="reco-controls">
                <Dropdown v-if="eligibleGroups.length" placement="bottom-start">
                    <template #button>
                        <div class="group-select-button">
                            <template v-if="group">
                                <template v-for="(value, index) in groupLabel(group)" :key="index">
                                    <PropertyValue :value="value" />
                                    <div v-if="index < groupLabel(group).length - 1" class="separator"></div>
                                </template>
                            </template>
                            <i class="bi bi-chevron-down ms-2"></i>
                        </div>
                    </template>
                    <template #popup="{ hide }">
                        <div class="group-select-popup">
                            <div
                                v-for="g in eligibleGroups"
                                :key="g.id"
                                class="group-select-item"
                                :class="{ 'is-selected': group && g.id === group.id }"
                                @click="selectGroup(g); hide()"
                            >
                                <template v-for="(value, index) in groupLabel(g)" :key="index">
                                    <PropertyValue :value="value" />
                                    <div v-if="index < groupLabel(g).length - 1" class="separator"></div>
                                </template>
                                <span class="text-secondary ms-1">({{ g.slots.length }})</span>
                            </div>
                        </div>
                    </template>
                </Dropdown>

                <div class="control-sep"></div>
                <ActionSelect action="similar" @changed="getReco" />

                <wTT message="main.recommand.filter">
                    <span class="tool" @click="toggleFilter">
                        <span :class="useFilter ? 'bi bi-funnel-fill text-primary' : 'bi bi-funnel'"></span>
                    </span>
                </wTT>
                <wTT message="main.recommand.reload">
                    <span class="tool" @click="getReco"><span class="bi bi-arrow-clockwise"></span></span>
                </wTT>
            </div>
        </div>

        <div v-if="!group" class="reco-empty text-secondary">{{ $t('main.reco.empty') }}</div>

        <!-- Top-level split: hero vs the whole panels block -->
        <div v-else class="stack" ref="stackRef">
            <div class="hero-slot" :style="heroStyle">
                <div class="hero">
                    <div ref="heroImageRef" class="hero-image">
                        <CenteredImage
                            v-if="hero && heroDims.height > 0"
                            :instance-id="hero.id"
                            :width="Math.max(heroDims.width - 16, 40)"
                            :height="Math.max(heroDims.height - 8, 40)"
                        />
                        <div v-else-if="!hero" class="hero-empty text-secondary">{{ $t('main.reco.no_more') }}</div>
                    </div>
                    <div v-if="hero" class="hero-actions">
                        <wTT message="main.recommand.accept">
                            <button class="accept" @click="acceptRecommend(hero)"><span class="bi bi-check-lg"></span></button>
                        </wTT>
                        <wTT message="main.recommand.refuse">
                            <button class="refuse" @click="refuseRecommend(hero)"><span class="bi bi-x-lg"></span></button>
                        </wTT>
                    </div>
                </div>
            </div>

            <div class="stack-handle resizable" @pointerdown="startHeroResize">
                <div class="stack-handle-line"></div>
            </div>

            <!-- Panels block: resize among themselves, collapsible -->
            <div class="panels" ref="panelsRef" :style="panelsStyle">
                <template v-for="(it, li) in panelItems" :key="it.key">
                    <div class="panel-slot" :style="panelSlotStyle(it.key)">
                        <RecoPanel
                            :title="$t(it.titleKey)"
                            :count="it.count"
                            :group-manager="it.manager"
                            :ready="it.ready"
                            :image-size="imageSize"
                            :input-key="it.inputKey"
                            :collapsed="collapsed[it.key]"
                            :empty-message="it.emptyKey ? $t(it.emptyKey) : undefined"
                            @toggle="toggleCollapse(it.key)"
                        />
                    </div>
                    <div
                        v-if="li < panelItems.length - 1"
                        class="stack-handle"
                        :class="{ resizable: showPanelHandle(li) }"
                        @pointerdown="showPanelHandle(li) && startPanelResize(li, $event)"
                    >
                        <div class="stack-handle-line"></div>
                    </div>
                </template>
            </div>
        </div>
    </div>
</template>

<style scoped>
.reco-workspace {
    display: flex;
    flex-direction: column;
    min-height: 0;
}

.reco-header {
    flex-shrink: 0;
    padding: var(--spacing-xs) var(--spacing-sm) var(--spacing-sm);
    border-bottom: 1px solid var(--border-color);
}

.reco-title {
    font-size: var(--font-size-md, 15px);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
    margin-bottom: var(--spacing-xs);
}

.reco-controls {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
}

.control-sep {
    width: 1px;
    align-self: stretch;
    background-color: var(--border-color);
    margin: 2px var(--spacing-xs);
}

.group-select-button {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    cursor: pointer;
    color: var(--text-secondary);
    transition: background-color var(--transition-fast);
}

.group-select-button:hover {
    background-color: var(--hover-bg);
}

.group-select-popup {
    display: flex;
    flex-direction: column;
    max-height: 400px;
    overflow-y: auto;
}

.group-select-item {
    display: inline-flex;
    align-items: center;
    padding: 4px 8px;
    cursor: pointer;
    white-space: nowrap;
    transition: background-color var(--transition-fast);
}

.group-select-item:hover {
    background-color: var(--hover-bg);
}

.group-select-item.is-selected {
    color: var(--primary);
    font-weight: var(--font-weight-medium);
}

.reco-empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
}

/* The stack fills all remaining space. */
.stack {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
}

/* Full-width slots so a panel (and its title) always spans the whole width,
   even when collapsed. */
.hero-slot,
.panel-slot {
    display: flex;
    flex-direction: column;
    min-height: 0;
    min-width: 0;
    overflow: hidden;
}

.panels {
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
}

.hero {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    padding: var(--spacing-sm) 0;
}

.hero-image {
    flex: 1;
    min-height: 0;
    display: flex;
    align-items: center;
    justify-content: center;
}

.hero-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
}

.hero-actions {
    display: flex;
    justify-content: center;
    gap: var(--spacing-md);
    padding-top: var(--spacing-sm);
    flex-shrink: 0;
}

.accept,
.refuse {
    width: 110px;
    height: 30px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-color);
    background: none;
    cursor: pointer;
    font-size: 16px;
    transition: background-color var(--transition-fast), color var(--transition-fast);
}

.accept {
    color: var(--text-success, #2e7d32);
    border-color: var(--validate-border);
}

.accept:hover {
    background-color: var(--validate-border);
}

.refuse {
    color: var(--text-danger, #c62828);
    border-color: var(--refuse-border);
}

.refuse:hover {
    background-color: var(--refuse-border);
}

/* Consistent thin gutter between every stack item (drag-resizable where the
   `resizable` class is set; a plain spacer otherwise). */
.stack-handle {
    position: relative;
    height: 6px;
    flex-shrink: 0;
}

.stack-handle.resizable {
    cursor: row-resize;
}

.stack-handle-line {
    position: absolute;
    left: 0;
    right: 0;
    top: 50%;
    height: 2px;
    transform: translateY(-50%);
    border-radius: 1px;
    background-color: transparent;
    transition: background-color var(--transition-fast);
}

.stack-handle.resizable:hover .stack-handle-line {
    background-color: var(--primary);
}

.tool {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    cursor: pointer;
}

.tool:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.separator {
    border-left: 2px solid var(--border-color);
    margin: 3px 4px;
}
</style>
