/**
 * Per-PropertyType value normalizer used when bucketing slots into groups.
 * Maps a raw column value to its group key (undefined/false for "no value").
 */
import { PropertyType } from "@/data/models";

export const valueParser: { [type in PropertyType]?: any } = {
    [PropertyType.checkbox]: (x?: boolean) => { if (!x) return false; return true },
    [PropertyType.color]:    (x?: number)  => { if (isNaN(x)) return undefined; return x },
    [PropertyType.date]:     (x?: Date)    => { if (!x) return undefined; return x },
    [PropertyType.number]:   (x?: number)  => { if (x == undefined) return undefined; return x },
    [PropertyType.path]:     (x?: string)  => { if (!x) return undefined; return x },
    [PropertyType.string]:   (x?: string)  => { if (!x) return undefined; return x },
    [PropertyType.url]:      (x?: string)  => { if (!x) return undefined; return x },
    [PropertyType._ahash]:   (x: string)   => x,
    [PropertyType._sha1]:    (x: string)   => x,
    [PropertyType._folders]: (x: number)   => x,
    [PropertyType._id]:      (x: number)   => x,
    [PropertyType._height]:  (x: number)   => x,
    [PropertyType._width]:   (x: number)   => x,
    [PropertyType.tag]:      (x: number[]) => { if (Array.isArray(x)) return x; return undefined },
    [PropertyType.multi_tags]:(x: number[])=> { if (Array.isArray(x)) return x; return undefined },
}
