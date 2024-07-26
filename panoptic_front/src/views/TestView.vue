<script setup lang="ts">
import TagBadge from "@/components/tagtree/TagBadge.vue";
import { useDataStore } from "@/data/dataStore";
import { Tag } from "@/data/models";
import { useProjectStore } from "@/data/projectStore";
import { deepCopy, sum } from "@/utils/utils";
import * as d3 from "d3";
import { computed, nextTick, onMounted, ref, watch } from "vue";

// const color = d3.scaleOrdinal(d3.schemeDark2)
// const background_color = "white"

// const renderChart = (data, options: any = {}) => {
//     options.color ||= (d, i) => color(i)

//     const tangleLayout = constructTangleLayout(deepCopy(data), options);

//     return `<svg width="${tangleLayout.layout.width}" height="${tangleLayout.layout.height
//         }" style="background-color: ${background_color}">
//   <style>
//     text {
//       font-family: sans-serif;
//       font-size: 10px;
//     }
//     .node {
//       stroke-linecap: round;
//     }
//     .link {
//       fill: none;
//     }
//   </style>

//   ${tangleLayout.bundles.map((b, i) => {
//             let d = b.links
//                 .map(
//                     l => `
//       M${l.xt} ${l.yt}
//       L${l.xb - l.c1} ${l.yt}
//       A${l.c1} ${l.c1} 90 0 1 ${l.xb} ${l.yt + l.c1}
//       L${l.xb} ${l.ys - l.c2}
//       A${l.c2} ${l.c2} 90 0 0 ${l.xb + l.c2} ${l.ys}
//       L${l.xs} ${l.ys}`
//                 )
//                 .join("");
//             return `
//       <path class="link" d="${d}" stroke="${background_color}" stroke-width="5"/>
//       <path class="link" d="${d}" stroke="${options.color(b, i)}" stroke-width="2"/>
//     `;
//         })}

//   ${tangleLayout.nodes.map(
//             n => `
//     <path class="selectable node" data-id="${n.id
//                 }" stroke="black" stroke-width="8" d="M${n.x} ${n.y - n.height / 2} L${n.x
//                 } ${n.y + n.height / 2}"/>
//     <path class="node" stroke="white" stroke-width="4" d="M${n.x} ${n.y -
//                 n.height / 2} L${n.x} ${n.y + n.height / 2}"/>

//     <text class="selectable" data-id="${n.id}" x="${n.x + 4}" y="${n.y -
//                 n.height / 2 -
//                 4}" stroke="${background_color}" stroke-width="2">${n.id}</text>
//     <text x="${n.x + 4}" y="${n.y -
//                 n.height / 2 -
//                 4}" style="pointer-events: none;">${n.id}</text>
//   `
//         )}

//   </svg>`;
// }

// const constructTangleLayout = (levels, options = {}) => {
//     // precompute level depth
//     levels.forEach((l, i) => l.forEach(n => (n.level = i)));

//     var nodes = levels.reduce((a, x) => a.concat(x), []);
//     var nodes_index = {};
//     nodes.forEach(d => (nodes_index[d.id] = d));

//     // objectification
//     nodes.forEach(d => {
//         d.parents = (d.parents === undefined ? [] : d.parents).map(
//             p => nodes_index[p]
//         );
//     });

//     // precompute bundles
//     levels.forEach((l, i) => {
//         var index = {};
//         l.forEach(n => {
//             if (n.parents.length == 0) {
//                 return;
//             }

//             var id = n.parents
//                 .map(d => d.id)
//                 .sort()
//                 .join('-X-');
//             if (id in index) {
//                 index[id].parents = index[id].parents.concat(n.parents);
//             } else {
//                 index[id] = { id: id, parents: n.parents.slice(), level: i, span: i - d3.min(n.parents, p => p.level) };
//             }
//             n.bundle = index[id];
//         });
//         l.bundles = Object.keys(index).map(k => index[k]);
//         l.bundles.forEach((b, i) => (b.i = i));
//     });

//     var links = [];
//     nodes.forEach(d => {
//         d.parents.forEach(p =>
//             links.push({ source: d, bundle: d.bundle, target: p })
//         );
//     });

//     var bundles = levels.reduce((a, x) => a.concat(x.bundles), []);

//     // reverse pointer from parent to bundles
//     bundles.forEach(b =>
//         b.parents.forEach(p => {
//             if (p.bundles_index === undefined) {
//                 p.bundles_index = {};
//             }
//             if (!(b.id in p.bundles_index)) {
//                 p.bundles_index[b.id] = [];
//             }
//             p.bundles_index[b.id].push(b);
//         })
//     );

//     nodes.forEach(n => {
//         if (n.bundles_index !== undefined) {
//             n.bundles = Object.keys(n.bundles_index).map(k => n.bundles_index[k]);
//         } else {
//             n.bundles_index = {};
//             n.bundles = [];
//         }
//         n.bundles.sort((a, b) => d3.descending(d3.max(a, d => d.span), d3.max(b, d => d.span)))
//         n.bundles.forEach((b, i) => (b.i = i));
//     });

//     links.forEach(l => {
//         if (l.bundle.links === undefined) {
//             l.bundle.links = [];
//         }
//         l.bundle.links.push(l);
//     });

//     // layout
//     const padding = 8;
//     const node_height = 22;
//     const node_width = 70;
//     const bundle_width = 14;
//     const level_y_padding = 16;
//     const metro_d = 4;
//     const min_family_height = 22;

//     options.c ||= 16;
//     const c = options.c;
//     options.bigc ||= node_width + c;

//     nodes.forEach(
//         n => (n.height = (Math.max(1, n.bundles.length) - 1) * metro_d)
//     );

//     var x_offset = padding;
//     var y_offset = padding;
//     levels.forEach(l => {
//         x_offset += l.bundles.length * bundle_width;
//         y_offset += level_y_padding;
//         l.forEach((n, i) => {
//             n.x = n.level * node_width + x_offset;
//             n.y = node_height + y_offset + n.height / 2;

//             y_offset += node_height + n.height;
//         });
//     });

//     var i = 0;
//     levels.forEach(l => {
//         l.bundles.forEach(b => {
//             b.x =
//                 d3.max(b.parents, d => d.x) +
//                 node_width +
//                 (l.bundles.length - 1 - b.i) * bundle_width;
//             b.y = i * node_height;
//         });
//         i += l.length;
//     });

//     links.forEach(l => {
//         l.xt = l.target.x;
//         l.yt =
//             l.target.y +
//             l.target.bundles_index[l.bundle.id].i * metro_d -
//             (l.target.bundles.length * metro_d) / 2 +
//             metro_d / 2;
//         l.xb = l.bundle.x;
//         l.yb = l.bundle.y;
//         l.xs = l.source.x;
//         l.ys = l.source.y;
//     });

//     // compress vertical space
//     var y_negative_offset = 0;
//     levels.forEach(l => {
//         y_negative_offset +=
//             -min_family_height +
//             d3.min(l.bundles, b =>
//                 d3.min(b.links, link => link.ys - 2 * c - (link.yt + c))
//             ) || 0;
//         l.forEach(n => (n.y -= y_negative_offset));
//     });

//     // very ugly, I know
//     links.forEach(l => {
//         l.yt =
//             l.target.y +
//             l.target.bundles_index[l.bundle.id].i * metro_d -
//             (l.target.bundles.length * metro_d) / 2 +
//             metro_d / 2;
//         l.ys = l.source.y;
//         l.c1 = l.source.level - l.target.level > 1 ? Math.min(options.bigc, l.xb - l.xt, l.yb - l.yt) - c : c;
//         l.c2 = c;
//     });

//     var layout = {
//         width: d3.max(nodes, n => n.x) + node_width + 2 * padding,
//         height: d3.max(nodes, n => n.y) + node_height / 2 + 2 * padding,
//         node_height,
//         node_width,
//         bundle_width,
//         level_y_padding,
//         metro_d
//     };

//     return { levels, nodes, nodes_index, links, bundles, layout };
// }

// const data = [
//     [{ id: 'a' }, { id: 'b' }, {id: 'e'}],
//     [{ id: 'c', parents: ['a', 'b'] }],
//     [{id: 'd', parents: ['a', 'c', 'e']}, {id: 'f', parents: ['e']}]
// ]

// const htmlData= ref('')
// onMounted(() => {
//     const svg = renderChart(data)
//     console.log(svg)
//     htmlData.value = svg
// })

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
        const valid = tags.filter(t => !t.children.some(c => depths[c] == undefined))
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
            for (const pId of tag.parents) {
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