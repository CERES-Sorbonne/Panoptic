<script setup lang="ts">
// Scratch page for plain HTML/CSS experiments, reachable at /#/test
// Nothing here is loaded by the main UI: no store, no router guard, no data.
// Edit freely, it is meant to be thrown away and rewritten.
</script>

<template>
    <div class="sandbox">
        <h1>Sandbox</h1>
        <p class="hint">Edit <code>src/views/SandboxView.vue</code>. Route: <code>/#/test</code></p>

        <div class="playground">
            <div class="frame">
                <input type="text" class="text-input" placeholder="type here" />
            </div>
        </div>
    </div>
</template>

<style scoped>
.sandbox {
    padding: 24px;
    font-family: system-ui, sans-serif;
    color: var(--text-color, #222);
}

.hint {
    color: var(--disabled-color, #888);
    font-size: 13px;
}

.playground {
    margin-top: 24px;
}

.frame {
    width: 300px;
    border: 1px solid black;
    /* no radius, and no padding so the input can fill it exactly */
}

.text-input {
    /* Safari/WebKit rounds native text fields; kill the default look */
    -webkit-appearance: none;
    appearance: none;
    border-radius: 0;
    display: block;
    box-sizing: border-box;
    width: 100%;
    padding: 6px 10px;
    margin: 0;
    border: 1px solid transparent;
    outline: none;
    background: transparent;
    font: inherit;
}

.text-input:hover,
.text-input:focus {
    border-color: #3b82f6;
}
</style>
