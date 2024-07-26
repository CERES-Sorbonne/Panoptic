<script setup lang="ts">
import TagBadge from "@/components/tagtree/TagBadge.vue";
import { useDataStore } from "@/data/dataStore";
import { Tag } from "@/data/models";
import { useProjectStore } from "@/data/projectStore";
import { deepCopy, sum } from "@/utils/utils";
import * as d3 from "d3";
import { computed, nextTick, onMounted, ref, watch } from "vue";


interface Line {
    x1: number
    y1: number
    x2: number
    y2: number
}

const project = useProjectStore()
const data = useDataStore()
const tagList = computed(() => data.tagList.filter(t => t.propertyId == 23))

const tagDepth = ref<{ [tagId: number]: number }>({})
const tagPosition = ref<{ [tagId: number]: number }>({})
const maxDepth = ref(0)
const lines = ref<Line[]>([])

let tagElems = {}
const tagColumns = ref<Tag[][]>([])

function computeTagColumns() {
    const res: Tag[][] = []
    for (let i = 0; i <= maxDepth.value; i++) {
        res[i] = tagList.value.filter(t => tagDepth.value[t.id] == i)
    }
    tagColumns.value = res
}

async function computeGraph() {
    const tags = tagList.value
    computeTagDepth(tags)
    computeTagColumns()
    await nextTick()
    computeLines()
}

function computeTagDepth(tags: Tag[]) {
    let depth = 0
    const depths = tagDepth.value
    while (tags.length) {
        const valid = tags.filter(t => !t.parents.some(c => depths[c] == undefined))
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
    const offset = 200
    const columns = tagColumns.value
    const res: Line[] = []
    for (const col of columns) {
        for (const tag of col) {
            if (!tag) continue
            for (const pId of tag.children) {
                // console.log(tagElems[tag.id])
                const t1 = tagElems[tag.id].getBoundingClientRect()
                const t2 = tagElems[pId].getBoundingClientRect()
                const line: Line = {
                    x1: t1.right - offset,
                    y1: t1.y + 11 - offset,
                    x2: t2.x - offset,
                    y2: t2.y + 11 - offset
                }
                res.push(line)
            }
        }
    }
    lines.value = res
}

async function reorderLines() {
    console.log('reorder')
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
        for (let i = 0; i < columns.length; i++) {
            columns[i] = columns[i].filter(t => t)
        }
        for (const col of columns) {
            for (let i = 0; i < col.length; i++) {
                const tag = col[i]
                indexes[tag.id] = i
            }
        }

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

function loggit(id) {
    console.log('click')
    console.log(tagElems[id].getBoundingClientRect().right)
}

function log() {
    console.log('lalala')
}

watch(() => project.status.loaded, computeGraph)

</script>

<template>
    <div style="position: relative; top:200px; left: 200px;">
        <svg width="5000" height="5000" style="position: absolute; top:0; z-index: 0;">
            <line v-for="l in lines" :x1="l.x1" :y1="l.y1" :x2="l.x2" :y2="l.y2" stroke="grey" />
        </svg>
        <div class="d-flex" style="z-index: 1; position: absolute;">
            <div v-for="tags in tagColumns" class="me-5">
                <div v-for="tag, i in tags" style="height: 25px;">
                    <span v-if="tag" :ref="e => tagElems[tag.id] = e">
                        <TagBadge :id="tag.id" @click="loggit(tag.id)" />
                        <!-- <div class="p-2" @click="log">{{ tag.id }} {{ tag.value }}</div> -->
                    </span>
                    <span v-else></span>
                </div>
            </div>
        </div>
    </div>
    <button @click="reorderLines">Reorder</button>
    <button @click="computeLines">compute lines</button>



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
</style>