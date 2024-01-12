<script setup>

import { onMounted, inject } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n({ useScope: 'global' })

const tours = inject('tours')

const steps = [
    {
        target: '#main-menu',
        content: t('tutorial.step-1'),
        params: {
            placement: "bottom",
            highlight: false
        }
    },
    {
        target: '#create-project',
        content: 'A small intro message on my project',        // params: {
        //     placement: "right"
        // }
    },
    {
        target: '#add-folder',
        content: 'A last message to the project',        // params: {
        //     placement: "right"
        // }
    },
]

onMounted(() => {
    tours.myTour.start()
})

</script>
<template>
    <v-tour name="myTour" :steps="steps"></v-tour>
</template>

<style>
/* .v-tour__target--highlighted {
  box-shadow: 0 0 0 99999px rgba(0,0,0,.4);
} */

.v-step__buttons{
    display: flex;
}

.v-step__button-skip{
    text-decoration: underline !important;
    border: none !important;
}
</style>