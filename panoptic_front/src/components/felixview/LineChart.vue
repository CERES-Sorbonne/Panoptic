<script setup>

import { tryOnBeforeMount } from '@vueuse/core';
import { defineProps, nextTick, onMounted, ref } from 'vue'

const props = defineProps({
    series: Array, // Spécifiez le type de la prop ici
    height: String
});


// Options du graphique
const chartOptions = {
    xaxis: {
        type: 'datetime',
        // min: props.series[0].data[0][0],
        // max: props.series[0].data[props.series[0].data.length - 1][0],
        // tickAmount: 1000,
    },
    chart: {
        stacked: false,
        stackOnlyBar: false,
        zoom: {
            type: "xy",
            autoScaleYaxis: true
        }
    },
    dataLabels: {
        enabled: false
    },
    stroke: {
        curve: 'smooth'
    },
    tooltip: {
        shared: false,
        custom: function ({ series, seriesIndex, dataPointIndex, w }) {
            const currentDataPoint = props.series[seriesIndex].data[dataPointIndex];

            let imagesHTML = '<div style="display: grid; grid-template-columns: repeat(3, 1fr); grid-gap: 5px;">';
            currentDataPoint.images.forEach((image, index) => {
                if (index < 9) { // Ne traiter que les 9 premières images
                    imagesHTML += `<div style="width: 75px; height: 75px;"><img src="${image}" style="width: 100%; height: 100%;" /></div>`;
                }
            });
            imagesHTML += '</div>';

            let tooltipHTML = `<span style="display: flex; align-items: center; justify-content: center;min-height:40px">${currentDataPoint.y} Images</span>`;
            // tooltipHTML += "<hr />"
            tooltipHTML += `<div>${imagesHTML}</div>`;

            return tooltipHTML;
        }
    }

};
</script>

<template>
    <apexchart :height="props.height" type="area" :options="chartOptions" :series="props.series"></apexchart>
</template>

  
<style scoped>
/* Ajoutez vos styles CSS ici si nécessaire */
</style>
  