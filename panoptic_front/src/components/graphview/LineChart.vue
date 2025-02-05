<script setup>

import { ref } from 'vue'
import { PropertyType } from '@/data/models';

const props = defineProps({
    chartData: {
        series: Array,
        xValues: Array,
        dataType: PropertyType
    }, // Spécifiez le type de la prop ici
    height: String
});

const reRenderKey = ref(0)
const stacked = ref(false);
const visibleImages = {}

Object.keys(props.chartData.series).forEach(seriesIndex => {
    visibleImages[seriesIndex] = false
})

// Options du graphique
const chartOptions = ref({
    markers: { size: 7 },
    legend: {
        showForSingleSeries: true,
        onItemClick: {
            toggleDataSeries: false
        },
    },
    xaxis: {
        type: props.chartData.dataType === PropertyType.date ? 'datetime' : 'numeric',
        categories: props.chartData.xValues,
        // min: props.series[0].data[0][0],
        // max: props.series[0].data[props.series[0].data.length - 1][0],
        // tickAmount: 1000,
    },
    chart: {
        type: "area",
        stacked: false,
        stackOnlyBar: false,
        zoom: {
            type: "x",
            autoScaleYaxis: true
        },
        animations: {
            animateGradually: {
                enabled: false,
                delay: 150
            },
        },
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

            let imagesHTML = '<div style="display: grid; grid-template-columns: repeat(5, 1fr); grid-gap: 5px;">';
            currentDataPoint.images.forEach((image, index) => {
                if (index < 10) { // Ne traiter que les 9 premières images
                    imagesHTML += `<div style="width: 75px; height: 75px;"><img src="${image}" style="width: 100%; height: 100%;" /></div>`;
                }
            });
            imagesHTML += '</div>';

            let tooltipHTML = `<span style="display: flex; align-items: center; justify-content: center;min-height:40px"><b>${props.chartData.series[seriesIndex].name} — </b> ${currentDataPoint.y} Images</span>`;
            // tooltipHTML += "<hr />"
            tooltipHTML += `<div>${imagesHTML}</div>`;

            return tooltipHTML;
        }
    }

});
const toggleStacked = () => {
    chartOptions.value.chart.stacked = !chartOptions.value.chart.stacked;
    stacked.value = !stacked.value
    reRenderKey.value += 1
};

const changeAreaToHisto = () => {
    let newValue;
    if (chartOptions.value.chart.type === "area") {
        newValue = {
            chart: {
                ...chartOptions.value.chart,
                type: "bar"
            },
        }
    }
    else {
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

const onLegendClick = (chartContext, seriesIndex, config) => {
    // chartContext.toggleSeries(chartContext.w.globals.seriesNames[seriesIndex]);
    const maxImages = 17;
    const series = props.chartData.series[seriesIndex];
    let maxY = Math.max(...series.data.map(el => el.y))
    // Supprimez les images précédentes
    document.querySelectorAll('.apexcharts-custom-image').forEach(el => el.remove());
    if (visibleImages[seriesIndex]) {
        visibleImages[seriesIndex] = false
        return
    }
    // Ajoutez des images pour chaque point de données
    series.data.forEach((point, pointIndex) => {
        const imgSize = 40;
        // le nombre d'images du datapoint est fait relativement au plus grand datapoint
        const nbImages = Math.floor((point.y / maxY) * maxImages)
        const images = point.images.slice(0, nbImages); // Limitez à 20 images
        const query = `circle[index="${seriesIndex}"][j="${pointIndex}"]`
        const circle = document.querySelector(query)
        const xStart = parseFloat(circle.getAttribute('cx'));
        // const yPos = parseFloat(circle.getAttribute('cy'));
        // const yOffset = ( images.length * 25 ) / 2
        // const chartHeight = chartContext.w.globals.svgHeight;
        images.forEach((url, i) => {
            const img = document.createElement('img');
            img.src = url;
            img.width = imgSize;
            img.height = imgSize;
            img.style.position = 'absolute';
            let xPos = xStart + imgSize / 1.5
            let yPos = 65 + (i * imgSize)
            img.style.left = `${xPos}px`;
            // img.style.top = `${yPos - yOffset + (i * 32)}px`;
            img.style.bottom = `${yPos}px`;
            img.classList.add('apexcharts-custom-image');
            img.addEventListener('mouseover', (e) => showZoomedImage(xPos, yPos, url));
            img.addEventListener('mouseout', hideZoomedImage);
            chartContext.el.appendChild(img);
        });
    });
    Object.keys(visibleImages).forEach(key => visibleImages[key] = false)
    visibleImages[seriesIndex] = true
}

function showZoomedImage(x, y, url) {
    const zoomedImg = document.getElementById('zoomed-image');
    zoomedImg.style.left = `${x + 120 * 1.5}px` // Positionner à côté du pointeur de la souris
    zoomedImg.src = url;
    zoomedImg.style.bottom = `${y}px` // Positionner à côté du pointeur de la souris
    zoomedImg.style.display = 'block';
}

function hideZoomedImage() {
    const zoomedImg = document.getElementById('zoomed-image');
    zoomedImg.style.display = 'none';
}
</script>

<template>
    <div style="display:flex">
        <button class="mt-2" @click="changeAreaToHisto">{{ chartOptions.chart.type === "area" ? $t("main.graph-view.histo")
            : $t("main.graph-view.curve") }}</button>
        <button v-if="props.chartData.series.length > 1" class="mt-2" style="margin-left: 1em" @click="toggleStacked">{{
            stacked ? $t("main.graph-view.over") : $t("main.graph-view.stack") }}</button>
    </div>
    <apexchart style="position:relative" :key=reRenderKey :height="props.height" :type="chartOptions.chart.type"
        :options="chartOptions" :series="props.chartData.series" @legendClick="onLegendClick"></apexchart>
    <i class="info">{{ $t("main.graph-view.info") }}</i>
    <img id="zoomed-image"
        style="display:none; position:absolute; z-index:1000; width:120px; height:120px; pointer-events:none;" />
</template>

  
<style>
.apexcharts-custom-image {
    /* pointer-events: none; */
    z-index: 500;
    transition: transform 0.15s ease, z-index 0s 0.3s;
}

/* .image-hover:hover {
    transform: scale(3);
    transition: transform 0s ease, z-index 0s 0s;
    z-index: 1000;
} */

.apexcharts-legend-text:hover {
    cursor: pointer;
}

.info {
    text-align: center;
    display: inherit;
    font-size: 0.8em;
}
</style>
  