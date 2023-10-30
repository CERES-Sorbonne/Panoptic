<script setup lang="ts">
import { Property, PropertyType, Tag } from '@/data/models';
import { globalStore } from '@/data/store';
import { computed, nextTick, onMounted, ref } from 'vue';
import TagBadge from '../tagtree/TagBadge.vue';
import TagOptionsDropdown from '../dropdowns/TagOptionsDropdown.vue';


const props = defineProps({
    property: Object as () => Property
})

const emits = defineEmits([''])

defineExpose({
    focus
})

const searchElem = ref(null)

const tagFilter = ref('')


const tagProposals = ref(null);
const selectedIndex = ref(0)

const isCreatePossible = computed(() => tagFilter.value.length > 0 && !filteredTagList.value.some(t => t.value == tagFilter.value))

const isCreateSelected = computed(() => selectedIndex.value == filteredTagList.value.length && isCreatePossible.value)

const tags = computed(() => globalStore.tags[props.property.id])
const filteredTagList = computed(() => {
    let filtered = Object.values(tags.value).filter((tag: Tag) => tag.value.toLowerCase().includes(tagFilter.value.toLowerCase()));
    return filtered

})

function focus() {
    nextTick(() => {
        if (!searchElem.value) return
        searchElem.value.focus()
    })
}

onMounted(() => {
    if (props.property.type != PropertyType.multi_tags && props.property.type != PropertyType.tag) {
        throw 'TagDropdown got propertyId that does not correspond to a tag | multi_tags type..\nGiven type: ' + props.property.type
    }
})

const optionClass = (id: number) => {
    let bg = selectedIndex.value == id ? 'bg-selected' : 'bg-white'
    return bg
}

const removeTag = async (tag: Tag) => {
};


function moveSelected(value: number) {
    let bonus = isCreatePossible.value ? 0 : -1
    if (value > 0 && selectedIndex.value < filteredTagList.value.length + bonus) {
        selectedIndex.value += 1
    }
    else if (value < 0 && selectedIndex.value > 0) {
        selectedIndex.value -= 1
    }
}


const selectOption = async function () {
    let valueToAdd: number
    // should we create the tag first ? 
    if (isCreateSelected.value) {
        const newTag = await globalStore.addTag(props.property.id, tagFilter.value);
        valueToAdd = newTag.id
    }
    else if (selectedIndex.value < filteredTagList.value.length) {
        let selectedTag = filteredTagList.value[selectedIndex.value]
        // Open Tag Modal ?
    }
    tagFilter.value = ''
    focus()
}

</script>

<template>
    <ul class="m-0 p-0">
        <div class="w-100 mb-1">
            <input type="text" class="w-100" v-model="tagFilter" ref="searchElem" style="font-size: 13px;"
                @keydown.down="moveSelected(1)" @keydown.up="moveSelected(-1)" @keydown.enter="selectOption" />
        </div>

        <ul class="list-unstyled pb-0">
            <!-- <p class="m-0 ms-2 me-2 text-muted text-nowrap" style="font-size: 14px;">Select a tag or create one
            </p> -->
            <li @mouseover="selectedIndex = index" :class="optionClass(index)"
                v-for="tag, index in filteredTagList" style="cursor: pointer;"><a class="ms-2" href="#">
                    <TagBadge :tag="tag.value" :color="tag.color" />
                    <span :style="{color: (selectedIndex == index) ? 'var(--text-color)': 'white'}" class="float-end" >
                        <!-- <i class="bi bi-three-dots sm-btn me-1"></i> -->
                        <TagOptionsDropdown :property-id="property.id" :tag-id="tag.id"/>
                    </span>
                </a>
            </li>
            <li @mouseover="selectedIndex = filteredTagList.length" @click.prevent.stop="selectOption"
                v-if="isCreatePossible" :class="optionClass(filteredTagList.length)" style="cursor: pointer;">
                <span class="text-muted ms-1">Create </span>
                <TagBadge :tag="tagFilter" :color="-1" />
            </li>
        </ul>
    </ul>
</template>

<style scoped>
.list {
    max-height: 400px;
    overflow-y: scroll;
    scrollbar-width: none;
}

.list::-webkit-scrollbar {
    display: none;
}

li {
    padding: 2px 0px;
    border-radius: 3px;

}
</style>