<script setup>
import { defineProps, ref, computed } from 'vue';

const props = defineProps({
    file: { type: Object, required: true },
    isLast: { type: Boolean, required: false }
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
        <div class="file-info">
            <i v-if="file.extension === 'dir'" class="bi bi-folder"></i>
            <i v-else-if="file.extension === 'disk'" class="bi bi-hdd"></i>
            <i v-else class="bi bi-file-earmark"></i>
            <span class="file-name">{{ file.name }}</span>
            <div v-if="file.images > 0" class="image-info">
                <i class="bi bi-images"></i>
                <sup>{{ file.images }}</sup>
            </div>
        </div>
    </li>
</template>

<style scoped>
/* Ajout de styles pour l'interaction hover */
.list-group-item {
    position: relative;
    /* Assurez-vous que la position est relative pour que les éléments absolus soient positionnés par rapport à cela */
}

.list-group-item:hover {
    cursor: pointer;
    background-color: #f8f9fa;
}

.file-info {
    display: flex;
    align-items: center;
    gap: 0.5em;
}

.file-name {
    flex-grow: 1;
    /* Faites en sorte que le nom du fichier occupe tout l'espace disponible */
    overflow: hidden;
    /* Masquez le texte dépassant */
    white-space: nowrap;
    /* Empêchez le texte de passer à la ligne */
    text-overflow: ellipsis;
    /* Ajoutez des points de suspension si le texte dépasse */
}

.image-info {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    margin-right: -0.5rem;
    font-size: 1em;
}

.image-info sup {
    margin-left: 0.3em;
    font-size: 0.7em;
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
}
</style>