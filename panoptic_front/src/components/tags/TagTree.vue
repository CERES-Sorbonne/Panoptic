<script setup lang="ts">
import TagBadge from "@/components/tagtree/TagBadge.vue";
import { deletedID, useDataStore } from "@/data/dataStore";
import { Property, Tag } from "@/data/models";
import { useProjectStore } from "@/data/projectStore";
import { sum } from "@/utils/utils";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import wTT from '@/components/tooltips/withToolTip.vue'


interface Line {
    x1: number
    y1: number
    x2: number
    y2: number
    child: Tag
    parent: Tag
    hover: boolean
}

const project = useProjectStore()
const data = useDataStore()

const props = defineProps<{
    property: Property
    selectedTags: Tag[]
}>()

const emits = defineEmits(['select', 'unselect'])

const tagDepth = ref<{ [tagId: number]: number }>({})
const maxDepth = ref(0)
const lines = ref<Line[]>([])
const tagFilter = ref(false)
const mainElem = ref(null)
let offset = { x: 0, y: 0 }

let tagElems = {}
const tagColumns = ref<Tag[][]>([])

const isDrawing = ref(false)
const hoveredTag = ref(-1)
const sourceTag = ref(-1)
const drawSource = ref([0, 0])
const drawTarget = ref([0, 0])
const colElem = ref(null)
const scrollElem = ref(null)


const selectedIndex = computed(() => {
    const res: {[id: number]: boolean} = {}
    props.selectedTags.forEach(t => res[t.id] = true)
    return res
})

const tagList = computed(() => {
    let res = data.tagList.filter(t => t.propertyId == props.property.id && t.id != deletedID)
    if (tagFilter.value && props.selectedTags.length) {
        const valid = new Set<number>()
        const selected = res.filter(t => selectedIndex.value[t.id])
        selected.forEach(t => valid.add(t.id))
        selected.forEach(t => t.allChildren.forEach(c => valid.add(c)))
        selected.forEach(t => t.allParents.forEach(c => valid.add(c)))
        res = data.tagList.filter(t => valid.has(t.id))
    }
    return res
})

function computeTagColumns() {
    const res: Tag[][] = []
    for (let i = 0; i <= maxDepth.value; i++) {
        res[i] = tagList.value.filter(t => tagDepth.value[t.id] == i)
    }
    tagColumns.value = res
}

async function computeGraph() {
    const rect = mainElem.value.getBoundingClientRect()
    offset.x = rect.x
    offset.y = rect.y
    const tags = tagList.value
    computeTagDepth(tags)
    computeTagColumns()
    await nextTick()
    updateSvgWidth()
    await nextTick()
    computeLines()
    await nextTick()
    await reorderLines()
}

function computeTagDepth(tags: Tag[]) {
    let depth = 0
    const depths = tagDepth.value
    const filtered = new Set(tags.map(t => t.id))
    while (tags.length) {
        const valid = tags.filter(t => !t.parents.some(c => depths[c] == undefined && filtered.has(c)))
        for (let tag of valid) {
            depths[tag.id] = depth
        }
        tags = tags.filter(t => depths[t.id] == undefined)
        depth += 1
    }
    maxDepth.value = depth - 1
    tagDepth.value = depths
}

function computeLines() {
    const columns = tagColumns.value
    const res: Line[] = []
    for (const col of columns) {
        for (const tag of col) {
            if (!tag) continue
            for (const pId of tag.children) {
                if (!tagElems[tag.id] || !tagElems[pId]) continue

                const t1 = tagElems[tag.id].getBoundingClientRect()
                const t2 = tagElems[pId].getBoundingClientRect()
                const line: Line = {
                    x1: t1.right - offset.x,
                    y1: t1.y + 11 - offset.y,
                    x2: t2.x - offset.x,
                    y2: t2.y + 11 - offset.y,
                    child: data.tags[pId],
                    parent: tag,
                    hover: false
                }
                res.push(line)
            }
        }
    }
    lines.value = res
}

async function reorderLines() {
    let columns = [...tagColumns.value]
    tagColumns.value = []
    await nextTick()
    tagColumns.value = columns
    for (let n = 0; n < 5; n++) {
        columns = [...tagColumns.value]
        const newColums: Tag[][] = []
        const maxTagCount = Math.max(...columns.map(c => c.length))
        const indexes: { [tagId: number]: number } = {}
        const goals: { [tagId: number]: number } = {}
        const finalGoal: { [tagId: number]: number } = {}
        // remove empty filles
        for (let i = 0; i < columns.length; i++) {
            columns[i] = columns[i].filter(t => t)
        }
        // map the position inside the columns for each tag
        for (const col of columns) {
            for (let i = 0; i < col.length; i++) {
                const tag = col[i]
                indexes[tag.id] = i
            }
        }

        // find the ideal position in the column
        for (const col of columns) {
            for (let i = 0; i < col.length; i++) {
                const tag = col[i]
                let middle = i
                if (!tag.children.length && tag.parents.length) {
                    middle = sum(tag.parents.map(p => indexes[p])) / tag.parents.length
                }
                else if (tag.children.length) {
                    middle = sum(tag.children.map(p => indexes[p])) / tag.children.length
                }
                goals[tag.id] = middle
            }

            const sorted = [...col].sort((t1, t2) => goals[t1.id] - goals[t2.id])

            // convert the goal position to a real index position inside the column array
            // the max length of a column is the length of the longest column
            let freeSpace = maxTagCount - sorted.length - 1
            let index = 0
            for (const tag of sorted) {
                while ((Math.round(goals[tag.id]) > index) && freeSpace > 0) {
                    freeSpace -= 1
                    index += 1
                }
                finalGoal[tag.id] = index
                index += 1
            }
            sorted.sort((a, b) => finalGoal[a.id] - finalGoal[b.id])
            // fill column data with "undefined" values as fillers for empty indexes
            const resCol: Tag[] = []
            let resIndex = 0
            for (const tag of sorted) {
                while (finalGoal[tag.id] > resIndex) {
                    resCol.push(undefined)
                    resIndex += 1
                }
                resCol.push(tag)
                indexes[tag.id] = resCol.length - 1
                resIndex += 1
            }
            newColums.push(resCol)
        }
        tagColumns.value = newColums
    }

    await nextTick()
    computeLines()
}

function onLineHover(index: number) {
    const line = lines.value[index]
    line.hover = true
}

function onLineEndHover(index: number) {
    const line = lines.value[index]
    line.hover = false
}

async function deleteLine(index: number) {
    const line = lines.value[index]
    await data.deleteTagParent(line.child.id, line.parent.id)
    await reDraw()
}

async function reDraw() {
    lines.value = []
    tagColumns.value = []
    tagDepth.value = {}
    await nextTick()
    await computeGraph()
}

const tagClass = computed(() => {
    let res = {}
    for (let tag of tagList.value) {
        res[tag.id] = []
        if (hoveredTag.value == tag.id) {
            res[tag.id].push('hover-tag')
        } else if (selectedIndex.value[tag.id]) {
            res[tag.id].push('selected-tag')
        } else {
            res[tag.id].push('tag')
        }
    }
    return res
})

const selectedLines = computed(() => {
    const res = []
    const valid = new Set<number>()
    const list = props.selectedTags.map(t => t.id)
    list.forEach(t => valid.add(t))
    list.forEach(t => data.tags[t].allChildren.forEach(c => valid.add(c)))
    list.forEach(t => data.tags[t].allParents.forEach(p => valid.add(p)))
    for (const line of lines.value) {
        if (valid.has(line.child.id) && valid.has(line.parent.id)) {
            res.push(true)
        } else {
            res.push(false)
        }
    }
    return res
})

const svgHeight = computed(() => {
    const max = Math.max(...tagColumns.value.map(c => c.length))
    return Math.max(0, max * 25)
})

const svgWidth = ref(100)

function updateSvgWidth() {
    const elem = colElem.value
    const width = elem.getBoundingClientRect().width
    svgWidth.value = Math.max(0, width)
}

function onClickTag(tag: Tag) {
    document.addEventListener('mouseup', endDraw)
    document.addEventListener('mousemove', followMouse)
    sourceTag.value = tag.id
    isDrawing.value = true

    const xScroll = scrollElem.value.scrollLeft
    const yScroll = scrollElem.value.scrollTop

    const rect = tagElems[tag.id].getBoundingClientRect()
    drawSource.value = [((rect.x + rect.right) / 2) - offset.x + xScroll, rect.y + 11 - offset.y + yScroll]
    drawTarget.value = drawSource.value
}

function onSelectTag(tag: Tag) {
    const selected = selectedIndex.value
    if (isDrawing.value && sourceTag.value != tag.id) return
    if (selected[tag.id]) {
        emits('select', props.selectedTags.filter(t => t.id != t.id))
    } else {
        emits('select', [...props.selectedTags, tag])
    }
    if (tagFilter.value) {
        reDraw()
    }
}

function followMouse(e) {
    const xScroll = scrollElem.value.scrollLeft
    const yScroll = scrollElem.value.scrollTop
    drawTarget.value = [e.clientX - offset.x + xScroll, e.clientY - offset.y + yScroll]
}

async function endDraw() {
    const source = sourceTag.value
    const target = hoveredTag.value

    sourceTag.value = -1
    isDrawing.value = false
    document.removeEventListener('mouseup', endDraw)
    document.removeEventListener('mousemove', followMouse)

    await nextTick()

    if (source != target && target > -1) {
        await data.addTagParent(target, source)
        lines.value = []
        tagColumns.value = []
        tagDepth.value = {}
        await nextTick()
        await computeGraph()
    }
}

function toggleFilter() {
    tagFilter.value = !tagFilter.value
    reDraw()
}

function clearSelected() {
    emits('unselect')

    if (tagFilter.value) {
        reDraw()
    }
}

async function mergeSelected() {
    const list = props.selectedTags.map(t => t.id)
    await data.mergeTags(list)
    const first = list[0]
    clearSelected()
    reDraw()
    onSelectTag(data.tags[first])
}

onMounted(computeGraph)
watch(() => project.status.loaded, computeGraph)
watch(() => props.property, reDraw)
watch(() => data.onUndo, reDraw)

</script>

<template>
    <div class="h-100">
        <div class="d-flex ms-2" style="padding: 6px 0px 2px 0px; height: 36px; border-right: 1px solid var(--border-color);">
            <div v-if="!props.selectedTags.length"><div class="text-secondary">{{  $t('modals.tags.click_to_select') }}</div></div>
            <div @click="toggleFilter" class="bbb me-1" v-if="props.selectedTags.length">
                <wTT message="modals.tags.filter_tree">
                    <i v-if="!tagFilter" class="bi bi-funnel"></i>
                    <i v-else class="bi bi-funnel-fill text-primary"></i>
                </wTT>
            </div>
            <div class="bbb" v-if="props.selectedTags.length" @click="clearSelected">
                <wTT message="modals.tags.unselect_tree">
                    <i class="bi bi-x" /> {{ props.selectedTags.length }} selected
                </wTT>
            </div>
            <div class="bbb ms-1" v-if="props.selectedTags.length > 1" @click="mergeSelected">
                <wTT message="modals.tags.merge_tree">
                    <span>Fusion</span> <span class="ms-1"><TagBadge :id="props.selectedTags[0].id" /></span>
                </wTT>
            </div>
        </div>
        <div class="ms-2 main-container" ref="scrollElem">
            <div style="position: absolute; user-select: none;" ref="mainElem">
                <svg :width="svgWidth" :height="svgHeight" style="position: absolute; top:0; z-index: 2;">
                    <template v-for="l, i in lines">
                        <line v-if="!selectedLines[i]" :x1="l.x1" :y1="l.y1" :x2="l.x2" :y2="l.y2" class="line" />
                    </template>
                    <template v-for="l, i in lines">
                        <line v-if="selectedLines[i]" :x1="l.x1" :y1="l.y1" :x2="l.x2" :y2="l.y2"
                            class="selected-line" />
                    </template>
                    <template v-for="l in lines">
                        <line v-if="l.hover" :x1="l.x1" :y1="l.y1" :x2="l.x2" :y2="l.y2" class="hover-line" />
                    </template>
                    <line v-for="l, i in lines" :x1="l.x1" :y1="l.y1" :x2="l.x2" :y2="l.y2"
                        style="stroke: white; stroke-width: 4; opacity: 0; cursor: pointer;"
                        @mouseenter="onLineHover(i)" @mouseleave="onLineEndHover(i)" @click="deleteLine(i)" />

                    <line v-if="isDrawing" :x1="drawSource[0]" :y1="drawSource[1]" :x2="drawTarget[0]"
                        :y2="drawTarget[1]" stroke="green" stroke-width="2" />
                </svg>
                <div class="d-flex m-2" style="z-index: 1;" ref="colElem">
                    <div v-for="tags in tagColumns" class="me-5">
                        <div v-for="tag, i in tags" style="height: 25px;">
                            <span v-if="tag" :ref="e => tagElems[tag.id] = e">
                                <TagBadge :id="tag.id" style="z-index: 10;" @mousedown="onClickTag(tag)"
                                    @mouseup="onSelectTag(tag)" @mouseenter="hoveredTag = tag.id"
                                    @mouseleave="hoveredTag = -1" :class="tagClass[tag.id]" />
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <!-- <div v-html="htmlData"></div> -->

</template>

<style scoped>
text {
    font-family: sans-serif;
    font-size: 10px;
}

.node {
    stroke-linecap: round;
}

.link {
    fill: none;
}

.line {
    stroke: grey
}

.selected-line {
    stroke: rgb(31, 221, 31);
}

.hover-line {
    stroke: red;
    stroke-width: 2px;
}

.tag {
    box-shadow: none;
}

.selected-tag {
    box-shadow: 0px 0px 5px 2px green;
}

.hover-tag {
    box-shadow: 0px 0px 10px 0px gray;
}

.main-container {
    position: relative;
    border: solid 1px var(--border-color);
    height: calc(100% - 50px);
    /* width: calc(100% -0px); */
    overflow: auto;
}
</style>