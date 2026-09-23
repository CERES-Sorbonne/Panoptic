export interface Tag {
    id: number;
    propertyId: number;
    parents: number[];
    value: string;
    color?: number;
    children?: number[]
    count?: number
    deleted?: boolean

    allParents?: number[]
    allChildren?: number[]

    // Derived by buildTagTree: the acyclic subset of `parents` actually used to build the
    // tree, and the edges dropped because they would have closed a loop. `parents` itself
    // stays raw — it is what the backend stores and what a commit sends back.
    effectiveParents?: number[]
    ignoredParents?: number[]
}

export interface TagIndex {
    [tagId: number]: Tag
}

export interface DeleteTagResult {
    tagId: number
    updatedValues: any[]
    updatedTags: Tag[]
}

export function buildTag(id: number, propertyId: number, value: string, parents?: number[], color: number = -1) {
    const resolvedColor = color === -1 ? Math.floor(Math.random() * 12) % 12 : color
    return { id, propertyId, value, parents: parents ?? [], color: resolvedColor }
}
