<script setup>

import { onMounted, inject } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n({ useScope: 'global' })

const tours = inject('tours')
const props = defineProps({
    tutorial: {
        type: String,
        default: "home"
    }    
})

const steps_home = [
    {
        target: '#main-menu',
        content: t('tutorial.step-1'),
        params: {
            placement: "top",
        }
    },
    {
        target: '#create-project',
        content: t('tutorial.step-2'),
        hideNext: true,
        params: {
            placement: "right",
        }
    },
    {
        target: '#select-folder',
        content: t('tutorial.step-3'),
        hideNext: true,
        params: {
            placement: "top",
        }
    },
    {
        target: '#confirm-modal',
        content: t('tutorial.step-3a'),
        hideNext: true,
        before: () => new Promise((resolve, reject) => {
            setTimeout(() => resolve('foo'), 300)
        }),
        params:{
            placement: "right"
        }
    },
    {
        target: '#confirm-create',
        hideNext: true,
        content: t('tutorial.step-3b'),
    }
]

const step_projects = [
    {
        target: '#add_folder',
        content: t('tutorial.step-4'),
        hideNext: true,
        params: {
            placement: "bottom",
        }
    },
    {
        target: '#confirm-modal',
        content: t('tutorial.step-4b'),
        hideNext: true,
        before: () => new Promise((resolve, reject) => {
            setTimeout(() => resolve('foo'), 300)
        }),
        params: {
            placement: "bottom",
        }
    },
    {
        target: '#import',
        content: t('tutorial.step-5'),
        params: {
            placement: "right",
        }
    },
    {
        target: '#add-property',
        content: t('tutorial.step-6'),
        hideNext: true,
        params: {
            placement: "right",
        }
    },
    {
        target: '#select-property',
        content: t('tutorial.step-7'),
        hideNext: true,
        before: () => new Promise((resolve, reject) => {
            setTimeout(() => resolve('foo'), 300)
        }),
        params: {
            placement: "right",
        }
    },
    {
        target: '#confirm-property',
        content: t('tutorial.step-8'),
        hideNext: true,
        params: {
            placement: "right",
        }
    },
    {
        target: '#main-content',
        content: t('tutorial.step-9'),
        hideNext: true,
        params: {
            placement: "top",
        }
    },

]

const steps = props.tutorial === 'home' ? steps_home : step_projects

onMounted(() => {
    tours.myTour.start()
})

</script>
<template>
    <v-tour name="myTour" :steps="steps" :options="{enabledButtons: {buttonPrevious: false}}">
        <template #default="tour">
                <v-step
                    v-if="tour.steps[tour.currentStep]"
                    :key="tour.currentStep"
                    :step="tour.steps[tour.currentStep]"
                    :previous-step="tour.previousStep"
                    :next-step="tour.nextStep"
                    :stop="tour.stop"
                    :skip="tour.skip"
                    :is-first="tour.isFirst"
                    :is-last="tour.isLast"
                    :labels="tour.labels"
                    :id="tour.currentStep"
                >
                    <template #actions
                                    v-if="steps[tour.currentStep].hideNext === true">
                        <div class="v-step__buttons">
                            <button @click="tour.skip" v-if="!tour.isLast"
                            class="v-step__button v-step__button-skip">{{ "Skip" }}</button>
                            <button @click.prevent="tour.nextStep" v-if="!tour.isLast"
                            class="v-step__button v-step__button-next" style="display: none !important">{{ "Next" }}</button>
                        </div>
                    </template>
                </v-step>
        </template>
  </v-tour>
</template>

<style lang="scss">


.v-step__button-skip{
    text-decoration: underline !important;
    border: none !important;
}

.v-step__button {
  background: transparent;
  border: .05rem solid white;
  border-radius: .10px;
  color: white;
  cursor: pointer;
  display: inline-block;
  font-size: .8rem;
  height: 1.8rem;
  line-height: 10px;
  outline: none;
  margin: 0 0.2rem;
  padding: .35rem .4rem;
  text-align: center;
  text-decoration: none;
  transition: all .2s ease;
  vertical-align: middle;
  white-space: nowrap;

  &:hover {
    background-color: rgba(white, 0.95);
    color: #50596c;
  }
}

// .v-tour__target--highlighted {
//   /* box-shadow: 0 0 0 99999px rgba(0,0,0,.4); */
//   /* border-radius: 25px; */
//   /* padding: 2em; */
//   border: none !important
// }

.v-step__buttons{
    display: flex;
    align-items: center;
    justify-content: center;
}

</style>