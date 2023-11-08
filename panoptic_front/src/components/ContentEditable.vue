
<style scoped></style>

<template>
  <component :is="tag" :contenteditable="contenteditable" @input="update" @blur="blur" @paste="onPaste"
    @keypress="onKeypress" @click.stop ref="element" @focus="emit('focus')">
  </component>
</template>

<script setup lang="ts">


import { defineProps, ref, computed, onMounted, watch } from 'vue';


function replaceAll(str: string, search: string, replacement: string) {
  return str.split(search).join(replacement);
}

const props = defineProps({
  'tag': String,
  'contenteditable': {
    type: [Boolean, String],
    default: true,
  },
  'modelValue': String,
  'noHtml': {
    type: Boolean,
    default: true,
  },
  'noNl': {
    type: Boolean,
    default: false,
  },
  'onlyNumber': Boolean

})

const emit = defineEmits({
  'returned': undefined,
  'update:modelValue': Object,
  'blur': undefined,
  'focus': undefined
})


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

defineExpose({
  focus
})


const element = ref<HTMLElement | null>()

function currentContent() {
  if (!element.value) {
    return ''
  }

  let res = props.noHtml ? element.value!.innerText : element.value!.innerHTML
  return res ?? ''
}

function updateContent(newcontent: string) {
  if (!element.value) return ''
  if (props.onlyNumber) {
    newcontent = newcontent.replace(/\D/g, '')
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
  emit('update:modelValue', currentContent());
}

function blur(event: any) {
  emit('blur')
  update(event)
}

function onPaste(event: any) {
  event.preventDefault();
  let text = (event.originalEvent || event).clipboardData.getData('text/plain');
  if (props.noNl) {
    text = replaceAll(text, '\r\n', ' ');
    text = replaceAll(text, '\n', ' ');
    text = replaceAll(text, '\r', ' ');
  }
  if (props.onlyNumber) {
    text = text.replace(/\D/g, '')
  }
  window.document.execCommand('insertText', false, text);
}
function onKeypress(event: any) {
  if (event.key == 'Enter' && props.noNl) {
    event.preventDefault();
    emit('returned', currentContent());
  }
  if (props.onlyNumber) {
    const res = event.key.replace(/\D/g, '')
    if (res == '') {
      event.preventDefault();
      emit('returned', currentContent());
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

watch(() => props.tag, (newval, oldval) => {
  updateContent(props.modelValue ?? '');
}, { flush: 'post' });

</script>
