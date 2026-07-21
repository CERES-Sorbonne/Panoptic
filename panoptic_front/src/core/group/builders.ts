/**
 * Group / GroupState / GroupOption factories.
 */
import { PropertyIndex, PropertyType, DateUnit } from "@/data/models";
import { SortDirection } from "../SortManager";
import { Group, GroupType, GroupOption, GroupSortType, GroupState } from "./types";

export function buildGroup(id: string | number, slots: number[], type: GroupType = GroupType.All): Group {
    return {
        id,
        key: [],
        slots,
        type,
        children: [],
        depth: 0,
        order: -1,
        start: 0,
        end: 0,
        meta: { propertyValues: [] },
        view: { closed: false, selected: false }
    } as Group
}

export function buildRoot(slots: number[]): Group {
    return buildGroup(0, slots)
}

export function buildGroupOption(propertyId: number, properties: PropertyIndex): GroupOption {
    const res: GroupOption = { direction: SortDirection.Ascending, type: GroupSortType.Property }
    const property = properties[propertyId]
    if (property.type == PropertyType.date) res.stepUnit = DateUnit.Day
    return res
}

export function createGroupState(): GroupState {
    return { groupBy: [], options: {}, sha1Mode: false }
}
