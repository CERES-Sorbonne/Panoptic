<script setup lang="ts">
import { adjustForTimezone, numberToString } from '@/utils/utils';
import { computed, nextTick, onMounted, reactive, ref } from 'vue';

const props = defineProps<{
    modelValue?: string,
    extended?: boolean
    autoFocus?: boolean
}>()
const emits = defineEmits(['update:modelValue', 'cancel', 'submit'])

const fields = ref({})
const fieldModels = ref({})
const fieldElems = ref({})
const format = ref('YMDhms')
const isoOrder = ref('YMDhms')
const resolution = ref(5)
const divElem = ref(null)

// define how many input slots for the date
// Right now hardcorded to 4 for positive years, and 1 additional for the minus for negative dates
// The minus is always in slot Y0
const yearsInputs = computed(() => {
    let f = fields.value
    if (f['Y0'] == '-') {
        return ['Y0', 'Y1', 'Y2', 'Y3', 'Y4']
    } else {
        return ['Y0', 'Y1', 'Y2', 'Y3']
    }
})

// build date object from fields
const localDate = computed<{
    date?: Date
    closest?: Date
}>(() => {
    let f = fields.value
    if (Object.values(f).some(v => v == 'x')) {
        return {}
    }

    const date = new Date()

    let yearStr = ''
    let nb = yearsInputs.value.length
    for (let i = 0; i < nb; i++) {
        yearStr += f['Y' + i]
    }

    let year = Number(yearStr)
    let month = Number('' + f['M0'] + f['M1']) - 1
    let day = Number('' + f['D0'] + f['D1'])
    let hour = Number('' + f['h0'] + f['h1'])
    let minute = Number('' + f['m0'] + f['m1'])
    let second = Number('' + f['s0'] + f['s1'])

    date.setUTCFullYear(year)
    date.setUTCMonth(month)
    date.setUTCDate(day)
    date.setUTCHours(hour)
    date.setUTCMinutes(minute)
    date.setUTCSeconds(second)

    if (date.getUTCDate() != day || date.getUTCMonth() != month) {
        return { closest: date }
    }

    return { date: date }
})

const viewFormat = computed(() => {
    const valid = isoOrder.value.substring(0, resolution.value + 1)
    return Array.from(format.value).filter(c => valid.includes(c))
})

function dateToString(date: Date) {
    let res = ''
    let form = viewFormat.value
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

// load date value into slots
// if date is not valid use x placeholders for every slot
function loadValue(toLoad: Date | string) {
    fields.value = {}
    let f = {}
    let date = new Date(toLoad)
    let r = resolution.value
    if (isNaN(+date)) {
        f['Y0'] = 'x'
        f['Y1'] = 'x'
        f['Y2'] = 'x'
        f['Y3'] = 'x'

        f['M0'] = r < 1 ? 0 : 'x'
        f['M1'] = r < 1 ? 1 : 'x'

        f['D0'] = r < 2 ? 0 : 'x'
        f['D1'] = r < 2 ? 1 : 'x'

        f['h0'] = r < 3 ? 0 : 'x'
        f['h1'] = r < 3 ? 0 : 'x'

        f['m0'] = r < 4 ? 0 : 'x'
        f['m1'] = r < 4 ? 0 : 'x'

        f['s0'] = r < 5 ? 0 : 'x'
        f['s1'] = r < 5 ? 0 : 'x'



        fields.value = f
        updateModels()
        return
    }
    // date = adjustForTimezone(date)

    // load day
    let day = numberToString(date.getUTCDate(), 2)
    f['D0'] = day[0]
    f['D1'] = day[1]
    // load month
    let month = numberToString(date.getUTCMonth() + 1, 2)
    f['M0'] = month[0]
    f['M1'] = month[1]

    // load year
    let year = numberToString(date.getUTCFullYear(), 4)
    for (let y = 0; y < year.length; y++) {
        f['Y' + y] = year[y]
    }

    // load hours
    let hours = numberToString(date.getUTCHours(), 2)
    f['h0'] = hours[0]
    f['h1'] = hours[1]

    // load minutes
    let minutes = numberToString(date.getUTCMinutes(), 2)
    f['m0'] = minutes[0]
    f['m1'] = minutes[1]

    // load minutes
    let seconds = numberToString(date.getUTCSeconds(), 2)
    f['s0'] = seconds[0]
    f['s1'] = seconds[1]

    fields.value = f
    updateModels()

}

function isNumberOrMinus(char: string) {
    if (char == '-') return true
    if (!isNaN(Number(char))) return true
    return false
}

// assign the fields to the fields models (used to bind the inputs)
// the fields variable acts as local truth, the fieldModels as interface to the html inputs
function updateModels() {
    fieldModels.value = Object.assign({}, fields.value)
}

// Used to remove the minus in case the user clicked on Y0
function clickYear(index: number) {
    if (index != 0) return
    if (fields.value['Y0'] != '-') return

    for (let i = 0; i < yearsInputs.value.length; i++) {
        fields.value['Y' + i] = fields.value['Y' + (1 + i)]
    }
    delete fields.value['Y' + (yearsInputs.value.length)]
    updateModels()
}

// Update a year slot
function updateYear(event, index: number, emit = true) {
    let data = event.data
    let key = 'Y' + index
    let f = fields.value
    if (data == null) data = '0'
    if (data.length > 1) {
        paste(key, data)
        return
    }

    if (!isNumberOrMinus(data)) {
        fieldModels.value[key] = fields.value[key]
        return
    }
    if (data == '-') {
        // if not already a negative year we add a minus in front and offset every field value to index+1
        // the fields between 1 and index are set to 0 as use the use wants to start writing the year from there
        if (f['Y0'] != '-') {
            let nb = yearsInputs.value.length
            for (let i = nb; i > 0; i--) {
                f['Y' + i] = f['Y' + (i - 1)]
            }
            f['Y0'] = '-'
            for (let i = 1; i <= index; i++) {
                f['Y' + i] = 0
            }
            fields.value = f
            updateModels()
            focusNextInput('Y' + (index))
        }
        // If the year is already negative fields between 1 and index are set to 0
        else {
            f['Y0'] = '-'
            for (let i = 1; i < index; i++) {
                f['Y' + i] = 0
            }
            fields.value = f
            updateModels()
        }
    } else {
        // If the user tries to override the minus without clicking on it we first remove the minus, then apply the write event
        // Can happen if you acces the minus fields with tab from another field without clicking on it
        if (f['Y0'] == '-' && index == 0) {
            clickYear(0)
            updateYear(event, 0)
            return
        }
        // normal case just write the data
        fields.value[key] = data
        fieldModels.value[key] = data
        focusNextInput(key)
    }

    if (emit) emits('update:modelValue', localDate.value.date?.toISOString())
}

function updateMonth(event, index: number, emit = true) {
    let data = event.data
    let key = 'M' + index
    let f = fields.value
    // on delete key press set to 0
    if (data == null) data = '0'
    if (data.length > 1) {
        paste(key, data)
        return
    }
    // if is valid number set the data
    if (!isNaN(data)) {
        f[key] = data
    }
    // verify the month is between 01 and 12
    if (f['M0'] > 1) f['M0'] = 0
    if (f['M0'] > 0 && f['M1'] > 2) {
        if (index == 0) f['M1'] = 2
        else f['M0'] = 0
    }
    if (f['M0'] == 0 && f['M1'] == 0) f['M1'] = 1
    fields.value = f
    updateModels()
    focusNextInput(key)
    if (emit) emits('update:modelValue', localDate.value.date?.toISOString())
}

function updateDay(event, index: number, emit = true) {
    let data = event.data
    let key = 'D' + index
    let f = fields.value
    // on delete key press set to 0
    if (data == null) data = '0'
    if (data.length > 1) {
        paste(key, data)
        return
    }
    // if is valid number set the data
    if (!isNaN(data)) {
        f[key] = data
    }
    // verify the day is between 01 and 31
    if (f['D0'] > 3) f['D0'] = 0
    if (f['D0'] == 3 && f['D1'] > 1) {
        if (index == 0) f['D1'] = 1
        else f['D0'] = 0
    }
    if (f['D0'] == 0 && f['D1'] == 0) f['D1'] = 1
    fields.value = f
    updateModels()
    focusNextInput(key)

    if (emit) emits('update:modelValue', localDate.value.date?.toISOString())
}

function updateHours(event, index: number, emit = true) {
    let data = event.data
    let key = 'h' + index
    let f = fields.value
    // on delete key press set to 0
    if (data == null) data = '0'
    if (data.length > 1) {
        paste(key, data)
        return
    }
    // if is valid number set the data
    if (!isNaN(data)) {
        f[key] = data
    }
    // verify the hour is between 00 and 23
    if (f['h0'] > 2) f['h0'] = 0
    if (f['h0'] == 2 && f['h1'] > 3) {
        if (index == 0) f['h1'] = 3
        else f['h0'] = 0
    }

    fields.value = f
    updateModels()
    focusNextInput(key)

    if (emit) emits('update:modelValue', localDate.value.date?.toISOString())
}
function updateMinutes(event, index: number, emit = true) {
    let data = event.data
    let key = 'm' + index
    let f = fields.value
    // on delete key press set to 0
    if (data == null) data = '0'
    if (data.length > 1) {
        paste(key, data)
        return
    }
    // if is valid number set the data
    if (!isNaN(data)) {
        f[key] = data
    }
    // verify the minute is between 00 and 59
    if (f['m0'] > 5) f['m0'] = 0

    fields.value = f
    updateModels()
    focusNextInput(key)

    if (emit) emits('update:modelValue', localDate.value.date?.toISOString())
}
function updateSeconds(event, index: number, emit = true) {
    let data = event.data
    let key = 's' + index
    let f = fields.value
    // on delete key press set to 0
    if (data == null) data = '0'
    if (data.length > 1) {
        paste(key, data)
        return
    }
    // if is valid number set the data
    if (!isNaN(data)) {
        f[key] = data
    }
    // verify the seconds is between 00 and 59
    if (f['s0'] > 5) f['s0'] = 0

    fields.value = f
    updateModels()
    focusNextInput(key)

    if (emit) emits('update:modelValue', localDate.value.date?.toISOString())
}

function onChangeFocus(key: string) {
    let f = fields.value
    if (f[key] == 'x') {
        f[key] = key == 'M1' || key == 'D1' ? 1 : 0
    }
    fields.value = f
    updateModels()
}

// focus the next field to edit
function focusNextInput(current: string) {
    let next = getNextFieldKey(current)
    if (next == undefined) return
    fieldElems.value[next].focus()
}

function getNextFieldKey(current: string) {
    let currentType = current[0]
    let currentIndex = Number(current.substring(1))

    let nbInputs = 2
    if (currentType == 'Y') nbInputs = yearsInputs.value.length

    if (currentIndex + 1 < nbInputs) {
        return currentType + (currentIndex + 1)
    }
    let order = viewFormat.value
    let index = order.indexOf(currentType)
    let next = order[index + 1]
    if (!next) return

    return next + '0'
}

function paste(key: string, data: string) {
    let i = 0
    let digits = Array.from(data).filter(c => c == '-' || !isNaN(Number(c))).filter(c => c != ' ')
    while (key && digits[i] != undefined) {
        let k = key[0]
        let ki = Number(key[1])
        if (k == 'Y') updateYear({ data: digits[i] }, ki, false)
        if (k == 'M') updateMonth({ data: digits[i] }, ki, false)
        if (k == 'D') updateDay({ data: digits[i] }, ki, false)

        if (k == 'h') updateHours({ data: digits[i] }, ki, false)
        if (k == 'm') updateMinutes({ data: digits[i] }, ki, false)
        if (k == 's') updateSeconds({ data: digits[i] }, ki, false)

        i += 1
        key = getNextFieldKey(key)
    }
    emits('update:modelValue', localDate.value.date?.toISOString())
}

function correctDate() {
    loadValue(localDate.value.closest)
    emits('update:modelValue', localDate.value.date?.toISOString())
}

function setDate(date) {
    loadValue(date)
    emits('update:modelValue', localDate.value.date?.toISOString())
}

function getNow() {
    var d = new Date()
    d.setTime(d.getTime() - d.getTimezoneOffset() * 60000)
    return d
}

async function autoFocus() {
    await nextTick()
    let inputs = divElem.value.getElementsByTagName('input')
    inputs[0].focus()
}

onMounted(() => {
    loadValue(props.modelValue)
    if (props.autoFocus) autoFocus()
})
</script>

<template>
    <div class="">
        <div class="d-flex flex-nowrap justify-content-center" style="line-height: 20px;" ref="divElem">
            <template v-for="data, formatIndex in viewFormat">
                <div v-if="data == 'Y'">
                    <div class="d-flex">
                        <input v-for="input, index in yearsInputs" class="digit" type=text
                            @input="e => updateYear(e, index)" v-model="fieldModels[input]"
                            :ref="e => fieldElems[input] = e" @click="clickYear(index)"
                            @keydown.delete.prevent.stop="updateYear({}, index)" @blur="onChangeFocus(input)" />
                    </div>
                    <div class="text-center text-secondary" style="font-size: 10px;">Y</div>
                </div>

                <div v-if="data == 'M'">
                    <div class="d-flex">
                        <input class="digit" type=text @input="e => updateMonth(e, 0)" v-model="fieldModels['M0']"
                            @blur="onChangeFocus('M0')" @keydown.delete.prevent.stop="updateMonth({}, 0)"
                            :ref="e => fieldElems['M0'] = e" />
                        <input class="digit" type=text @input="e => updateMonth(e, 1)" v-model="fieldModels['M1']"
                            @blur="onChangeFocus('M1')" @keydown.delete.prevent.stop="updateMonth({}, 1)"
                            :ref="e => fieldElems['M1'] = e" />
                    </div>
                    <div class="text-center text-secondary" style="font-size: 10px;">M</div>
                </div>

                <div v-if="data == 'D'">
                    <div class="d-flex">
                        <input class="digit" type=text @input="e => updateDay(e, 0)" v-model="fieldModels['D0']"
                            @blur="onChangeFocus('D0')" :ref="e => fieldElems['D0'] = e"
                            @keydown.delete.prevent.stop="updateDay({}, 0)" />
                        <input class="digit" type=text @input="e => updateDay(e, 1)" v-model="fieldModels['D1']"
                            @blur="onChangeFocus('D1')" :ref="e => fieldElems['D1'] = e"
                            @keydown.delete.prevent.stop="updateDay({}, 1)" />
                    </div>
                    <div class="text-center text-secondary" style="font-size: 10px;">D</div>
                </div>

                <div v-if="data == 'h'">
                    <div class="d-flex">
                        <input class="digit" type=text @input="e => updateHours(e, 0)" v-model="fieldModels['h0']"
                            @blur="onChangeFocus('h0')" @keydown.delete.prevent.stop="updateHours({}, 0)"
                            :ref="e => fieldElems['h0'] = e" />
                        <input class="digit" type=text @input="e => updateHours(e, 1)" v-model="fieldModels['h1']"
                            @blur="onChangeFocus('h1')" :ref="e => fieldElems['h1'] = e"
                            @keydown.delete.prevent.stop="updateHours({}, 1)" />
                    </div>
                    <div class="text-center text-secondary" style="font-size: 10px;">h</div>
                </div>

                <div v-if="data == 'm'">
                    <div class="d-flex">
                        <input class="digit" type=text @input="e => updateMinutes(e, 0)" v-model="fieldModels['m0']"
                            @blur="onChangeFocus('m0')" @keydown.delete.prevent.stop="updateMinutes({}, 0)"
                            :ref="e => fieldElems['m0'] = e" />
                        <input class="digit" type=text @input="e => updateMinutes(e, 1)" v-model="fieldModels['m1']"
                            @blur="onChangeFocus('m1')" @keydown.delete.prevent.stop="updateMinutes({}, 1)"
                            :ref="e => fieldElems['m1'] = e" />
                    </div>
                    <div class="text-center text-secondary" style="font-size: 10px;">m</div>
                </div>

                <div v-if="data == 's'">
                    <div class="d-flex">
                        <input class="digit" type=text @input="e => updateSeconds(e, 0)" v-model="fieldModels['s0']"
                            @blur="onChangeFocus('s0')" @keydown.delete.prevent.stop="updateSeconds({}, 0)"
                            :ref="e => fieldElems['s0'] = e" />
                        <input class="digit" type=text @input="e => updateSeconds(e, 1)" v-model="fieldModels['s1']"
                            @blur="onChangeFocus('s1')" @keydown.delete.prevent.stop="updateSeconds({}, 1)"
                            :ref="e => fieldElems['s1'] = e" />
                    </div>
                    <div class="text-center text-secondary" style="font-size: 10px;">s</div>
                </div>

                <div v-if="'YMD'.includes(viewFormat[formatIndex + 1])" class="slash">/</div>
                <div v-if="'YMD'.includes(viewFormat[formatIndex]) && 'hms'.includes(viewFormat[formatIndex + 1])"
                    class="me-2">
                </div>
                <div v-else-if="'hms'.includes(viewFormat[formatIndex + 1])">:</div>
            </template>
        </div>
        <div class="d-flex">
            <div><i class="bi bi-x bb" @click="setDate(undefined)" /></div>
            <div><i class="bi bi-calendar3 bb" @click="setDate(getNow())"></i></div>
            <!-- <div> <i class="bi bi-arrow-counterclockwise bb" @click="loadValue(props.modelValue)" /></div> -->
            <div class="ms-2">
                <div v-if="!localDate.closest && !localDate.date" style="width: 50px;" class="text-warning">{{ $t("none") }}
                </div>
                <div v-if="localDate.closest && !localDate.date" class="text-warning" style="width: 50px;">
                    {{ $t('datepicker.invalid') }}
                </div>
                <div v-if="localDate.date" style="width: 50px;">
                    <span class="text-success">
                        {{ $t('datepicker.valid') }}
                    </span>
                </div>
            </div>
            <div class="flex-grow-1"></div>
            <div v-if="props.extended"><span class="bb" @click="emits('cancel')">{{ $t('datepicker.cancel') }}</span>
            </div>
            <div v-if="props.extended"><span class="bb" @click="emits('submit')">{{ $t('datepicker.submit') }}</span>
            </div>
        </div>
        <div v-if="localDate.closest && !localDate.date" class="text-center">
            <span class="text-warning" style="cursor: pointer; font-size: 14px;" @click="correctDate">
                {{ $t('datepicker.correct') }}: {{ dateToString(localDate.closest) }} ?
            </span>
        </div>
    </div>
</template>

<style scoped>
.digit {
    /* background-color: bisque; */
    border-radius: 5px;
    overflow: hidden;
    /* margin-right: 1px; */
    /* border: 1px solid var(--border-color); */
    cursor: pointer;
}

input[type=text]:focus {
    background-color: lightgray;
}

/* input[type=text]:hover {
    background-color: lightgray;
    cursor: pointer;
} */

.slash {
    font-size: 18px;
    margin: 0px 1px;
    position: relative;
    top: 1.5px;
}

/* for chrome */
input[type=text]::-webkit-inner-spin-button,
input[type=text]::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
}


/* for mozilla */
input[type=text] {
    font-size: 14px;
    border: none;
    border-radius: 5px;
    text-align: center;
    width: 11.5px;
    -moz-appearance: textfield;
    caret-color: transparent;
}
</style>