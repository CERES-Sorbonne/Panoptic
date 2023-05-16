<!-- ./src/components/CustomSlider.vue -->
<script setup>

</script>

<template>
  <main>
    <input type="range" class="win10-thumb" min="50" max="200" value="25" step="1" />
  </main>
</template>


<style scoped lang="scss">
/* === range theme and appearance === */
input[type="range"] {
  font-size: 1.5rem;
  width: 12.5em;
}

input[type="range"] {
  color: #ef233c;
  --thumb-height: 1.125em;
  --track-height: 0.125em;
  --track-color: rgba(0, 0, 0, 0.2);
  --brightness-hover: 180%;
  --brightness-down: 80%;
  --clip-edges: 0.125em;
}

input[type="range"].win10-thumb {
  color: #2b2d42;

  --thumb-height: 12px;
  --thumb-width: 12px;
  --clip-edges: 0;
}

// @media (prefers-color-scheme: dark) {
//   html {
//     background-color: #000;
//   }

//   html::before {
//     background: radial-gradient(circle at center, #101112, #000);
//   }

//   input[type="range"] {
//     color: #f07167;
//     --track-color: rgba(255, 255, 255, 0.1);
//   }

//   input[type="range"].win10-thumb {
//     color: #3a86ff;
//   }
// }

/* === range commons === */
input[type="range"] {
  position: relative;
  background: #fff0;
  overflow: hidden;
}

input[type="range"]:active {
  cursor: grabbing;
}

input[type="range"]:disabled {
  filter: grayscale(1);
  opacity: 0.3;
  cursor: not-allowed;
}

/* === WebKit specific styles === */
input[type="range"],
input[type="range"]::-webkit-slider-runnable-track,
input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  transition: all ease 100ms;
  height: var(--thumb-height);
}

input[type="range"]::-webkit-slider-runnable-track,
input[type="range"]::-webkit-slider-thumb {
  position: relative;
}

input[type="range"]::-webkit-slider-thumb {
  --thumb-radius: calc((var(--thumb-height) * 0.5) - 1px);
  --clip-top: calc((var(--thumb-height) - var(--track-height)) * 0.5 - 0.5px);
  --clip-bottom: calc(var(--thumb-height) - var(--clip-top));
  --clip-further: calc(100% + 1px);
  --box-fill: calc(-100vmax - var(--thumb-width, var(--thumb-height))) 0 0 100vmax currentColor;

  width: var(--thumb-width, var(--thumb-height));
  background: linear-gradient(currentColor 0 0) scroll no-repeat left center / 50% calc(var(--track-height) + 2px);
  background-color: currentColor;
  box-shadow: var(--box-fill);
  border-radius: var(--thumb-width, var(--thumb-height));
  border: none;

  filter: brightness(100%);
  clip-path: polygon(100% -1px,
      var(--clip-edges) -1px,
      0 var(--clip-top),
      -100vmax var(--clip-top),
      -100vmax var(--clip-bottom),
      0 var(--clip-bottom),
      var(--clip-edges) 100%,
      var(--clip-further) var(--clip-further));
}

input[type="range"]:hover::-webkit-slider-thumb {
  filter: brightness(var(--brightness-hover));
  cursor: grab;
}

input[type="range"]:active::-webkit-slider-thumb {
  filter: brightness(var(--brightness-down));
  cursor: grabbing;
}

input[type="range"]::-webkit-slider-runnable-track {
  background: linear-gradient(var(--track-color) 0 0) scroll no-repeat center / 100% calc(var(--track-height) + 1px);
}

input[type="range"]:disabled::-webkit-slider-thumb {
  cursor: not-allowed;
}

/* === Firefox specific styles === */
input[type="range"],
input[type="range"]::-moz-range-track,
input[type="range"]::-moz-range-thumb {
  appearance: none;
  transition: all ease 100ms;
  height: var(--thumb-height);
}
</style>