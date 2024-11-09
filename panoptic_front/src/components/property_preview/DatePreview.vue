<script setup lang="ts">
import { numberToString } from '@/utils/utils';
import { computed } from 'vue';


const props = withDefaults(defineProps<{
    date?: string
    format?: string
    resolution?: number
}>(), {
    format: "YMDhms",
    resolution: 5
})

const dateString = computed(() => {
    let date = new Date(props.date)
    if (isNaN(+date)) {
        return undefined
    }
    return dateToString(date)
})

function dateToString(date: Date) {
    let res = ''
    let form = props.format
    for (let i = 0; i < form.length; i++) {
        let f = form[i]
        if (f == 'Y') res += numberToString(date.getUTCFullYear(), 4)
        if (f == 'M') res += numberToString(date.getUTCMonth() + 1, 2)
        if (f == 'D') res += numberToString(date.getUTCDate(), 2)
        if (f == 'h') res += numberToString(date.getUTCHours(), 2)
        if (f == 'm') res += numberToString(date.getUTCMinutes(), 2)
        if (f == 's') res += numberToString(date.getUTCSeconds(), 2)

        let nf = form[i + 1]
        if ('YMD'.includes(nf)) res += '/'
        if ('YMD'.includes(f) && 'hms'.includes(nf)) res += ' '
        else if (nf && 'hms'.includes(nf)) res += ':'
        else if (f == 'h' && nf == undefined) res += 'h'
    }
    return res
}

</script>

<template>
    <div>
        <span v-if="!dateString" class="text-secondary">{{ $t('none') }}</span>
        <span v-else>{{ dateString }}</span>
    </div>
</template>

<style scoped></style>