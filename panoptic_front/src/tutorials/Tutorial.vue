<script setup>

import { ModalId } from '@/data/models';
import { usePanopticStore } from '@/data/panopticStore';
import { useProjectStore } from '@/data/projectStore';
import { onMounted, inject, watch, nextTick, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n({ useScope: 'global' })

const panoptic = usePanopticStore()
const project = useProjectStore()

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
        params: {
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
        before: () => new Promise((resolve, reject) => {
            setTimeout(() => resolve('foo'), 300)
        }),
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
        before: () => new Promise((resolve, reject) => {
            setTimeout(() => resolve('foo'), 300)
        }),
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
            setTimeout(() => resolve('foo'), 250)
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
        params: {
            placement: "bottom",
        }
    },
    {
        target: '#main-content',
        content: t('tutorial.step-10'),
        params: {
            placement: "bottom",
        }
    },
    {
        target: '#add-group-button',
        content: t('tutorial.step-11'),
        params: {
            placement: "bottom",
        },
        hideNext: true,
    },
    {
        target: '#main-content',
        content: t('tutorial.step-12'),
        params: {
            placement: "bottom",
        },
    },
    {
        target: '#main-content',
        content: t('tutorial.step-13'),
        params: {
            placement: "bottom",
        },
    },
    {
        target: '#main-content',
        content: t('tutorial.step-13a'),
        params: {
            placement: "bottom",
        },
    },
    {
        target: '#selection-stamp',
        content: t('tutorial.step-13b'),
        params: {
            placement: "bottom",
        },
    },
    {
        target: '#remove-group-button',
        content: t('tutorial.step-14'),
        params: {
            placement: "top",
        },
    },
    {
        target: '#add-tab-button',
        content: t('tutorial.step-14b'),
        params: {
            placement: "bottom",
        },
    },
    {
        target: '#group-action-button',
        content: t('tutorial.step-15'),
        params: {
            placement: "bottom"
        }
    },
    {
        target: '#main-content',
        content: t('tutorial.step-16'),
        params: {
            placement: "bottom"
        }
    },
    {
        target: '#main-content',
        content: t('tutorial.step-17'),
        params: {
            placement: "bottom"
        }
    },

]

const steps = props.tutorial === 'home' ? steps_home : step_projects

let currentStep = parseInt(localStorage.getItem('currentStep') || '0')

const hasProjects = computed(() => Array.isArray(panoptic.data.status.projects) && panoptic.data.status.projects.length > 0)
const showTutorial = computed(() => ((!hasProjects.value && panoptic.data.init) || project.showTutorial))

watch(showTutorial, async () => {
    start()
})

onMounted(() => {
    start()
})

async function start() {
    if (showTutorial.value) {
        if(!hasProjects.value) {
            localStorage.setItem('tutorialFinished', 'false')
        }
        await nextTick()
        console.log(currentStep)
        if (currentStep === 5 && panoptic.openModalId === ModalId.PROPERTY && steps.length - 1 > currentStep) {
            tours.myTour.start(currentStep)
        }
        else {
            tours.myTour.start()
        }
    }

}

// Watch for changes in currentStep and update localStorage accordingly
function updateCurrentStep(newStep) {
    if (newStep !== -1 && newStep) {
        // localStorage.setItem('currentStep', newStep.toString())
        currentStep = newStep
    }
}

function notifyFinished() {
    localStorage.setItem('tutorialFinished', 'true')
}

</script>
<template>
    <v-tour v-if="showTutorial" name="myTour" :steps="steps"
        :options="{ enabledButtons: { buttonPrevious: false } }">
        <template #default="tour">
            <v-step v-if="tour.steps[tour.currentStep]" :key="tour.currentStep" :step="tour.steps[tour.currentStep]"
                :previous-step="tour.previousStep" :next-step="tour.nextStep" :stop="tour.stop" :skip="tour.skip"
                :is-first="tour.isFirst" :is-last="tour.isLast" :labels="tour.labels" :id="tour.currentStep">
                <template #actions v-if="steps[tour.currentStep].hideNext === true || tour.isLast">
                    <div class="v-step__buttons">
                        <button @click="tour.skip(); updateCurrentStep(-1); notifyFinished()" v-if="!tour.isLast"
                            class="v-step__button v-step__button-skip">{{ $t('tutorial.buttons.skip') }}</button>
                        <button @click="tour.nextStep(); updateCurrentStep(tour.currentStep + 1)" v-if="!tour.isLast"
                            class="v-step__button v-step__button-next"
                            :style="steps[tour.currentStep].hideNext ? 'display: none !important' : ''">{{
        $t('tutorial.buttons.next') }}</button>
                        <button class="v-step__button v-step__button-stop" v-if="tour.isLast" @click="tour.stop(); notifyFinished()">{{
                            $t('tutorial.buttons.finish') }}</button>
                    </div>
                </template>
            </v-step>
        </template>
    </v-tour>
</template>

<style lang="scss">
.v-step__button-skip {
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

.v-step__buttons {
    display: flex;
    align-items: center;
    justify-content: center;
}
</style>