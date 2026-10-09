// Date values as DatePreview prints them, out of the component so the scrollers' read-only cells
// can print the same text without mounting a DatePreview per cell.
import { numberToString } from '@/utils/utils'

// `format` lists the parts to print, in order: Y M D h m s. Undefined for a value that is not a
// date at all.
export function formatDate(value: string, format = 'YMDhms'): string | undefined {
    const date = new Date(value)
    if (isNaN(+date)) return undefined
    let res = ''
    for (let i = 0; i < format.length; i++) {
        const f = format[i]
        if (f == 'Y') res += numberToString(date.getUTCFullYear(), 4)
        if (f == 'M') res += numberToString(date.getUTCMonth() + 1, 2)
        if (f == 'D') res += numberToString(date.getUTCDate(), 2)
        if (f == 'h') res += numberToString(date.getUTCHours(), 2)
        if (f == 'm') res += numberToString(date.getUTCMinutes(), 2)
        if (f == 's') res += numberToString(date.getUTCSeconds(), 2)

        const nf = format[i + 1]
        if ('YMD'.includes(nf)) res += '/'
        if ('YMD'.includes(f) && 'hms'.includes(nf)) res += ' '
        else if (nf && 'hms'.includes(nf)) res += ':'
        else if (f == 'h' && nf == undefined) res += 'h'
    }
    return res
}
