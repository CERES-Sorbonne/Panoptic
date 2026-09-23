/**
 * Per-PropertyType value normalizer used when bucketing slots into groups.
 * Maps a raw column value to its group key (undefined/false for "no value").
 *
 * A numeric column stores "unset" as NaN in its raw buffer, but readSlot hands out null for the
 * same slot. Both paths feed these parsers (the full rebuild reads the buffer directly, the
 * incremental update goes through readSlot), so a numeric-backed parser must accept NaN, null and
 * undefined and collapse all three to the same key — otherwise the two paths mint two different
 * "no value" groups. undefined is that canonical key, as the tag, date and readSlot paths already
 * produce it.
 *
 * Note isNaN(null) is false while isNaN(undefined) is true: use isNoValue, never bare isNaN.
 */
import { PropertyType } from "@/data/models";

/**
 * True for every spelling of "no value": null, undefined, the empty string and a NaN numeric
 * slot. The single test shared by the parsers and by the views that ask whether a group is the
 * empty bucket. 0 and false are values, not "no value".
 */
export function isNoValue(x: any): boolean {
    return x == undefined || x === '' || (typeof x === 'number' && Number.isNaN(x))
}

export const valueParser: { [type in PropertyType]?: any } = {
    [PropertyType.checkbox]: (x?: boolean) => { if (!x) return false; return true },
    [PropertyType.color]:    (x?: number)  => { if (isNoValue(x)) return undefined; return x },
    [PropertyType.date]:     (x?: Date)    => { if (!x) return undefined; return x },
    [PropertyType.number]:   (x?: number)  => { if (isNoValue(x)) return undefined; return x },
    [PropertyType.path]:     (x?: string)  => { if (!x) return undefined; return x },
    [PropertyType.string]:   (x?: string)  => { if (!x) return undefined; return x },
    [PropertyType.url]:      (x?: string)  => { if (!x) return undefined; return x },
    [PropertyType._ahash]:   (x: string)   => x,
    [PropertyType._sha1]:    (x: string)   => x,
    [PropertyType._folders]: (x: number)   => x,
    [PropertyType._id]:      (x: number)   => { if (isNoValue(x)) return undefined; return x },
    [PropertyType._height]:  (x: number)   => { if (isNoValue(x)) return undefined; return x },
    [PropertyType._width]:   (x: number)   => { if (isNoValue(x)) return undefined; return x },
    [PropertyType.tag]:      (x: number[]) => { if (Array.isArray(x)) return x; return undefined },
    [PropertyType.multi_tags]:(x: number[])=> { if (Array.isArray(x)) return x; return undefined },
}
