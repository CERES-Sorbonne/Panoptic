<script setup>
import { active } from 'd3';
import { ref } from 'vue';

let konamiCode = ""
let rightPosition = ref(-1100)
let duckClass = ""

const secretCode = 'ArrowUpArrowUpArrowDownArrowDownArrowLeftArrowRightArrowLeftArrowRight';

window.addEventListener('keydown', async function (e) {
    konamiCode += e.key;
    if (secretCode.slice(0, konamiCode.length) !== konamiCode) {
        konamiCode = ""
    }
    if (konamiCode.length === secretCode.length) {
        if (konamiCode === secretCode) {
            duckClass = ""
            rightPosition.value = -300
            setTimeout(() => {
                duckClass = "active"
                rightPosition.value = -1100, 1500
            }, 1500)
            konamiCode = ""; // Réinitialiser le code Konami
        } else {
            konamiCode = ""
        }

    }
});
</script>

<template>
    <div id="duck-container" :style="{right: rightPosition.toString() + 'px'}" :class="duckClass">
        <img alt="Duck" class="logo" src="../assets/duck.svg"  :style="{height: '100vh'}"/>
    </div>
</template>

<style scoped>
    #duck-container{
        height: 100vh;
        position: fixed;
        z-index: 999;
        top: 0;
        transition: right 0.4s ease;
        transform: rotate(-45deg);
    }
    #duck-container.active{
        transition: right 4s ease;
    }
</style>