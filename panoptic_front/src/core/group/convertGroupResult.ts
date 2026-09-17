import { ActionContext, GroupResult, Sha1ToInstances } from "@/data/models"
import { useColumnStore } from "@/data/stores/columnStore"
import { convertScoreListToGroupScoreList, getTmpId } from "@/utils/utils"
import { buildGroup } from "./builders"
import { ClusterParam, Group, GroupType } from "./types"

function _idsToSlots(ids: number[]): number[] {
    const col = useColumnStore()
    const slots: number[] = []
    for (const id of ids) {
        const s = col.slotMap.get(id)
        if (s !== undefined) slots.push(s)
    }
    return slots
}

export function convertClusterGroupResult(groups: GroupResult[], ctx: ActionContext, funcInfo?: { function: string, inputs: ClusterParam[] }) {
    console.log(funcInfo)
    const col = useColumnStore()
    const sha1Index: { [sha1: string]: number[] } = {}
    for (const id of ctx.instanceIds) {
        const slot = col.slotMap.get(id)
        if (slot === undefined) continue
        const sha1 = col.sha1s()[slot]
        if (!sha1) continue
        if (!sha1Index[sha1]) sha1Index[sha1] = []
        sha1Index[sha1].push(id)
    }

    return groups.map((group) => {
        const ids: number[] = []
        if (group.ids) {
            ids.push(...group.ids)
        } else {
            group.sha1s.forEach(sha1 => sha1Index[sha1]?.forEach(id => ids.push(id)))
        }
        const res = buildGroup(getTmpId(), _idsToSlots(ids), GroupType.Cluster)
        res.meta.score = Math.round(group.score?.value ?? undefined)
        if (funcInfo) {
            res.meta.clusterFunction = funcInfo.function
            res.meta.clusterInputs = funcInfo.inputs
        }
        res.name = group.name
        res.isSha1Group = group.ids ? false : true
        res.score = group.score
        res.scores = convertScoreListToGroupScoreList(group, sha1Index)
        return res
    })
}

export function convertSearchGroupResult(groups: GroupResult[]) {
    const col = useColumnStore()

    return groups.map((group) => {
        const sha1Index: Sha1ToInstances = {}
        const ids: number[] = []
        if (group.ids) {
            ids.push(...group.ids)
        } else {
            for (const sha1 of (group.sha1s ?? [])) {
                const instanceIds = col.getInstancesBySha1(sha1)
                sha1Index[sha1] = instanceIds
                ids.push(...instanceIds)
            }
        }
        const res = buildGroup(0, _idsToSlots(ids), GroupType.Cluster)
        res.meta.score = Math.round(group.score?.value)
        res.name = group.name
        res.isSha1Group = !group.ids
        res.score = group.score
        res.scores = convertScoreListToGroupScoreList(group, sha1Index)
        return res
    })
}

export function sortGroupByScore(group: Group) {
    const col = useColumnStore()
    const ids = col.instanceIds()
    const dir = group.scores.maxIsBest ? -1 : 1
    group.slots.sort((s1, s2) => {
        return (group.scores.valueIndex[ids[s1]] - group.scores.valueIndex[ids[s2]]) * dir
    })
    return group
}
