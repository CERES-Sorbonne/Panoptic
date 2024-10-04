<script setup lang="ts">
import { defineProps, ref, onMounted, watch } from 'vue';

const props = withDefaults(defineProps<{
    modelValue: any,
    contenteditable?: boolean,
    noHtml?: boolean,
    noNl?: boolean,
    onlyNumber?: boolean
}>(), {
    contenteditable: true,
    noHtml: true
})

const emits = defineEmits<{
    returned: [value: string];
    'update:modelValue': [modelValue: any];
    blur: [];
    focus: [];
}>()

defineExpose({
    focus
})

const element = ref<HTMLElement>(null)

function focus() {
    setEndOfContenteditable(element.value)
    // element.value.focus()
}
function setEndOfContenteditable(contentEditableElement) {
    var range, selection;
    if (document.createRange)//Firefox, Chrome, Opera, Safari, IE 9+
    {
        range = document.createRange();//Create a range (a range is a like the selection but invisible)
        range.selectNodeContents(contentEditableElement);//Select the entire contents of the element with the range
        range.collapse(false);//collapse the range to the end point. false means collapse to end rather than the start
        selection = window.getSelection();//get the selection object (allows you to change selection)
        selection.removeAllRanges();//remove any selections already made
        selection.addRange(range);//make the range you have just created the visible selection
    }
}

function currentContent() {
    if (!element.value) {
        return ''
    }
    let res = props.noHtml ? element.value!.innerText : element.value!.innerHTML
    return res ?? ''
}

function cleanText(text: string) {
    if (props.onlyNumber) {
        text = text.replace(/[^\d.]/g, '')  // Remove everything except digits and periods
        text = text.replace(/\.(?=.*\.)/g, '');  // Remove all decimal points except the first one
    }
    if (!text) {
        text = ''
    }
    return text
}

function updateContent(newcontent: string) {
    if (props.onlyNumber) {
        newcontent = cleanText(newcontent)
    }
    if (props.noHtml) {
        element.value!.innerText = newcontent;
    }
    else {
        element.value!.innerHTML = newcontent;
    }
}

function update(event: any) {
    if (!element.value) return
    emits('update:modelValue', currentContent());
}

function blur(event: any) {
    emits('blur')
    update(event)
}

function onPaste(event: ClipboardEvent) {
    event.preventDefault();

    // Get the plain text from the clipboard
    let text = event.clipboardData?.getData('text/plain') || '';
    if (props.onlyNumber) {
        text = cleanText(text)
    }

    // Get the current selection
    const selection = window.getSelection();
    if (!selection?.rangeCount) return;

    const range = selection.getRangeAt(0);
    range.deleteContents(); // Optional: remove any selected content before inserting

    if (props.onlyNumber && currentContent().includes('.')) {
        text = text.replace(/\./g, '');
    }

    // Split the text by newlines to preserve line breaks
    const lines = text.split('\n');

    // Insert each line as a separate text node, adding <br> elements between lines
    lines.forEach((line, index) => {
        if (index > 0) {
            const br = document.createElement('br');
            range.insertNode(br);  // Add a <br> tag between lines
            range.setStartAfter(br);
        }
        const textNode = document.createTextNode(line);
        range.insertNode(textNode);
        range.setStartAfter(textNode);
    });

    // Remove existing selections and set the caret to the end
    selection.removeAllRanges();
    selection.addRange(range);
    emits('update:modelValue', currentContent())
}


function onKeypress(event: any) {
    if (event.key == 'Enter' && props.noNl) {
        event.preventDefault();
        emits('returned', currentContent());
    }
    if (props.onlyNumber) {
        let res = event.key.replace(/[^\d.]/g, '')
        if (res == '.' && currentContent().includes('.')) {
            res = ''
        }
        if (res == '') {
            event.preventDefault();
            emits('returned', currentContent());
        }
    }
}

onMounted(() => {
    updateContent(props.modelValue ?? '')
})

watch(() => props.modelValue, (newval, oldval) => {
    if (newval != currentContent()) {
        updateContent(newval ?? '')
    }
})

watch(() => props.noHtml, (newval, oldval) => {
    updateContent(props.modelValue ?? '')
})

</script>

<template>
    <div class="h-100 w-100" @click="focus">
        <div :contenteditable="contenteditable" @input="update" @blur="blur" @paste="onPaste" @keypress="onKeypress"
            @click.stop ref="element" @focus="emits('focus')">
        </div>
    </div>
</template>
