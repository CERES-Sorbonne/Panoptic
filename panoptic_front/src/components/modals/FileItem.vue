<script setup>
import { defineProps, ref, computed } from 'vue';

const props = defineProps({
    file: { type: Object, required: true },
    isLast: {type: Boolean, required: false}
});

const emit = defineEmits();

const onClick = () => {
    emit('itemClicked');
};

const itemClass = computed(() => {
    return {
        'list-group-item': true,
        active: props.file.active, // Ajoute la classe 'active' si l'élément est actif
        last: props.isLast
    };
});

</script>

<template>
    <li @click="onClick" :class="itemClass">
        <i v-if="file.extension === 'dir'" class="bi bi-folder"></i>
        <i v-else-if="file.extension === 'disk'" class="bi bi-hdd"></i>
        <i v-else class="bi bi-file-earmark"></i>
        {{ file.name.slice(0, 35) }}
        <div v-if="file.images > 0" class="image-info">
            <i class="bi bi-images"></i>
            <sup>{{ file.images }}</sup>
        </div>
    </li>
</template>

<style scoped>
/* Ajout de styles pour l'interaction hover */
.list-group-item:hover {
    cursor: pointer;
    background-color: #f8f9fa;
}

.image-info {
    display: flex;
    align-items: center;
    justify-content: right;
    margin-top: -1rem;
    /* Ajustez selon vos besoins pour aligner correctement le texte */
    margin-right: -0.5rem;
    font-size: 1em;
    /* Ajustez la taille du texte selon vos besoins */
}

.image-info sup {
    margin-left: 0.3em;
    font-size: 0.7em;
    /* Ajustez la taille du texte supérieur selon vos besoins */
}

.list-group-item.active:not(.last)::after {
    content: '';
    position: absolute;
    top: 50%;
    right: -11px;
    border-top: 11px solid transparent;
    /* Ajustez la taille du triangle selon vos besoins */
    border-bottom: 11px solid transparent;
    /* Ajustez la taille du triangle selon vos besoins */
    border-left: 11px solid #0d6efd;
    /* Couleur du triangle */
    transform: translateY(-50%);
}

.list-group-item.active:hover {
    cursor: pointer;
    background-color: #6599ce;
}

.list-group-item.active:not(.last):hover::after {
    border-left-color: #6599ce;
    /* Couleur du triangle lors du survol */
}</style>