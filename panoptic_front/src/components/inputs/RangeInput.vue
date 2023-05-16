<!-- ./src/components/CustomSlider.vue -->
<script setup>

import { ref, watchEffect } from "vue";

// define component props for the slider component
const { min, max, step, modelValue } = defineProps({
  min: {
    type: Number,
    default: 0,
  },
  max: {
    type: Number,
    default: 100,
  },
  step: {
    type: Number,
    default: 1,
  },
  modelValue: {
    type: Number,
    default: 50,
  },
});

// define emits for the slider component
const emit = defineEmits(["update:modelValue"]);

// define refs for the slider component
const sliderValue = ref(modelValue);
const slider = ref(null);

// function to get the progress of the slider
const getProgress = (value, min, max) => {
  return ((value - min) / (max - min)) * 100;
};

// function to set the css variable for the progress
const setCSSProgress = (progress) => {
  slider.value.style.setProperty("--ProgressPercent", `${progress}%`);
};

// watchEffect to update the css variable when the slider value changes
watchEffect(() => {
  if (slider.value) {
    // emit the updated value to the parent component
    emit("update:modelValue", sliderValue.value);

    // update the slider progress
    const progress = getProgress(
      sliderValue.value,
      slider.value.min,
      slider.value.max
    );

    // define extrawidth to ensure that the end of progress is always under the slider thumb.
    // let extraWidth = (100 - progress) / 10;
    let extraWidth = 0

    // set the css variable
    setCSSProgress(progress + extraWidth);
  }
});

let isWebkit = false
if(navigator.userAgent.indexOf('AppleWebKit') != -1){
    isWebkit = true
}
</script>
<template>
  <div class="custom-slider">
    <input
      ref="slider"
      :value="sliderValue"
      @input="({ target }) => (sliderValue = parseFloat(target.value))"
      type="range"
      :min="min"
      :max="max"
      :step="step"
      class="slider"
      :style="isWebkit ? 'top:-5px' : ''"
    />
  </div>
</template>
<style scoped>
.custom-slider {
  --trackHeight: 3px;
  --thumbRadius: 11px;
  --dark-color: rgb(120, 137, 150);
  --ligth-color: rgb(216, 222, 226);
}

/* style the input element with type "range" */
.custom-slider input[type="range"] {
  position: relative;
  appearance: none;
  /* pointer-events: none; */
  border-radius: 999px;
  width: 200px;
  z-index: 0;
}

/* ::before element to replace the slider track */
.custom-slider input[type="range"]::before {
  content: "";
  position: absolute;
  width: var(--ProgressPercent, 100%);
  height: 100%;
  background: var(--dark-color);
  /* z-index: -1; */
  pointer-events: none;
  border-radius: 999px;
}

/* `::-webkit-slider-runnable-track` targets the track (background) of a range slider in chrome and safari browsers. */
.custom-slider input[type="range"]::-webkit-slider-runnable-track {
  appearance: none;
  background: var(--ligth-color);
  height: var(--trackHeight);
  border-radius: 999px;
}

/* `::-moz-range-track` targets the track (background) of a range slider in Mozilla Firefox. */
.custom-slider input[type="range"]::-moz-range-track {
  background: var(--ligth-color);
  height: var(--trackHeight);
  border-radius: 999px;
}

.custom-slider input[type="range"]::-moz-range-thumb {
  background: var(--dark-color);
  height: var(--thumbRadius);
  width: var(--thumbRadius);
  border-radius: 999px;
  border: none;
}

.custom-slider input[type="range"]::-webkit-slider-thumb {
  appearance: none;
  position: relative;
  /* top: 50%; 
  transform: translate(0, -50%);
  */
  width: var(--thumbRadius);
  height: var(--thumbRadius);
  margin-top: calc((var(--trackHeight) - var(--thumbRadius)) / 2);
  background: var(--dark-color);
  border-radius: 999px;
  pointer-events: all;
  z-index: 1;
}

.custom-slider input[type="range"]::-moz-range-progress {
    background: var(--dark-color);
}

</style>