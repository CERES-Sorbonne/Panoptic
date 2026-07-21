/**
 * Date bucket arithmetic — zero Date allocations in the group scan loop.
 * Bucket key is a plain integer; the display Date range is computed once per unique key.
 */
import { DateUnit, DateUnitFactor } from "@/data/models";

export function dateBucketKey(date: Date | undefined, stepSize: number, unit: DateUnit): number | undefined {
    if (!date) return undefined
    if (!stepSize) stepSize = 1
    if (!unit) unit = DateUnit.Day
    if (unit === DateUnit.Year) {
        return Math.floor(date.getUTCFullYear() / stepSize)
    }
    if (unit === DateUnit.Month) {
        const totalMonths = date.getUTCFullYear() * 12 + date.getUTCMonth()
        return Math.floor(totalMonths / stepSize)
    }
    // Second, Minute, Hour, Day, Week — DateUnitFactor is in seconds
    const stepMs = stepSize * DateUnitFactor[unit] * 1000
    return Math.floor(date.getTime() / stepMs)
}

export function dateBucketRange(key: number, stepSize: number, unit: DateUnit): { first: Date, last: Date } {
    if (!stepSize) stepSize = 1
    if (unit === DateUnit.Year) {
        const year = key * stepSize
        return {
            first: new Date(Date.UTC(year, 0, 1)),
            last:  new Date(Date.UTC(year + stepSize, 0, 1))
        }
    }
    if (unit === DateUnit.Month) {
        const startMonth = key * stepSize
        const endMonth   = startMonth + stepSize
        return {
            first: new Date(Date.UTC(Math.floor(startMonth / 12), startMonth % 12, 1)),
            last:  new Date(Date.UTC(Math.floor(endMonth   / 12), endMonth   % 12, 1))
        }
    }
    // Sub-day: epoch-ms arithmetic
    const stepMs = stepSize * DateUnitFactor[unit] * 1000
    return { first: new Date(key * stepMs), last: new Date(key * stepMs + stepMs - 1) }
}
