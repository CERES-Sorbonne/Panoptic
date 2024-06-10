<script setup>

import { tryOnBeforeMount } from '@vueuse/core';
import { defineProps, nextTick, onMounted, ref} from 'vue'

const props = defineProps({
    chartData: {
        series: Array,
        data: Array
    }, // Spécifiez le type de la prop ici
    height: String
});

console.log(props.chartData.series)
const reRenderKey = ref(0)
// Options du graphique
const chartOptions = ref({
    markers:{size: 7},
    xaxis: {
        type: 'datetime',
        categories: props.chartData.dates,
        // min: props.series[0].data[0][0],
        // max: props.series[0].data[props.series[0].data.length - 1][0],
        // tickAmount: 1000,
    },
    chart: {
        type: "area",
        stacked: false,
        stackOnlyBar: false,
        zoom: {
            type: "xy",
            autoScaleYaxis: true
        },
        animations: {
            animateGradually: {
                enabled: false,
                delay: 150
            },
        }
    },
    dataLabels: {
        enabled: false
    },
    stroke: {
        curve: 'straight'
    },
    tooltip: {
        // followCursor: true,
        intersect: true,
        shared: false,
        custom: function ({ series, seriesIndex, dataPointIndex, w }) {
            const currentDataPoint = props.chartData.series[seriesIndex].data[dataPointIndex];
            // console.log(currentDataPoint)

            let imagesHTML = '<div style="display: grid; grid-template-columns: repeat(3, 1fr); grid-gap: 5px;">';
            currentDataPoint.images.forEach((image, index) => {
                if (index < 16) { // Ne traiter que les 9 premières images
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

});
const toggleStacked = () => {
    chartOptions.value.chart.stacked = !chartOptions.value.chart.stacked;
    reRenderKey.value += 1
};

const changeAreaToHisto = () => {
    let newValue;
    if(chartOptions.value.chart.type === "area"){
        newValue = {
                chart: {
                    ...chartOptions.value.chart,
                    type: "bar"
                },
        }
    }
    else{
        newValue = {
            chart: {
                ...chartOptions.value.chart,
                type: "area",
            },
        }
    }
    chartOptions.value = {
        ...chartOptions.value,
        ...newValue
    }
    reRenderKey.value += 1
}
</script>

<template>
    <div style="display:flex">
        <button class="mt-2" @click="changeAreaToHisto">{{ chartOptions.chart.type === "area" ? "Histogramme" : "Courbe"}}</button>
        <button v-if="props.chartData.series.length > 1" class="mt-2" style="margin-left: 1em" @click="toggleStacked">Stacker</button>
    </div>
    <apexchart :key=reRenderKey :height="props.height" :type="chartOptions.chart.type" :options="chartOptions" :series="props.chartData.series"></apexchart>
</template>

  
<style scoped>
/* Ajoutez vos styles CSS ici si nécessaire */
</style>
  