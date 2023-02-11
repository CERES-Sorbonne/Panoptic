
<script setup>
import ImageList from '../components/ImageList.vue'
</script>

<template>
  <main>
      <div class="row">
        <div class="col-3 bg-dark">
          Ici une barre de menu
        </div>
        <div class="col-9">
          <ul class="nav nav-tabs">
            <li class="nav-item">
              <a class="nav-link active" aria-current="page" href="#">Active</a>
            </li>
            <li class="nav-item">
              <a class="nav-link" href="#">Link</a>
            </li>
            <li class="nav-item">
              <a class="nav-link" href="#">Link</a>
            </li>
            <li class="nav-item">
              <a class="nav-link disabled">Disabled</a>
            </li>
          </ul>
        </div>
        <ImageList />
      </div>

  </main>
</template>
