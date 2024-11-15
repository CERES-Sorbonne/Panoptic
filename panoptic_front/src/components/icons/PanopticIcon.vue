<template>
    <div class="eye-container">
      <svg ref="svgElement" viewBox="0 0 200 100">
        <!-- Oeil gauche (ovale) -->
        <ellipse 
          cx="75" 
          cy="50" 
          :rx="25" 
          :ry="isBlinking ? 3 : 35" 
          fill="white" 
          stroke="black" 
          stroke-width="3"
        />
        <circle :cx="leftPupil.x" :cy="leftPupil.y" r="10" fill="black"/>
  
        <!-- Oeil droit (ovale) -->
        <ellipse 
          cx="125" 
          cy="50" 
          :rx="25" 
          :ry="isBlinking ? 3 : 35" 
          fill="white" 
          stroke="black" 
          stroke-width="3"
        />
        <circle :cx="rightPupil.x" :cy="rightPupil.y" r="10" fill="black"/>
      </svg>
    </div>
  </template>
  
  <script setup>
  import { ref, onMounted, onUnmounted } from 'vue';
  
  const leftPupil = ref({ x: 75, y: 50 });
  const rightPupil = ref({ x: 125, y: 50 });
  
  const leftEye = { cx: 75, cy: 50, maxDistance: 15 };
  const rightEye = { cx: 125, cy: 50, maxDistance: 15 };
  
  const isBlinking = ref(false);
  const svgElement = ref(null)

  const handleMouseMove = (event) => {
    const svgRect = svgElement.value.getBoundingClientRect();
  
    const updatePupil = (eye, pupilRef, mouseX, mouseY) => {
      const dx = mouseX - (svgRect.left + eye.cx);
      const dy = mouseY - (svgRect.top + eye.cy);
  
      const angle = Math.atan2(dy, dx);
      const distance = Math.min(eye.maxDistance, Math.sqrt(dx * dx + dy * dy));
  
      pupilRef.value.x = eye.cx + distance * Math.cos(angle);
      pupilRef.value.y = eye.cy + distance * Math.sin(angle);
    };
  
    const mouseX = event.clientX;
    const mouseY = event.clientY;
  
    updatePupil(leftEye, leftPupil, mouseX, mouseY);
    updatePupil(rightEye, rightPupil, mouseX, mouseY);
  };
  
  // Fonction pour déclencher un clignement
  const triggerBlink = () => {
    isBlinking.value = true;
    setTimeout(() => {
      isBlinking.value = false;
      scheduleNextBlink();
    }, 200); // Durée du clignement (200 ms)
  };
  
  // Planifie le prochain clignement dans un intervalle de 5 à 10 secondes
  const scheduleNextBlink = () => {
    const blinkInterval = Math.random() * (10000 - 5000) + 5000; // Intervalle entre 5s et 10s
    setTimeout(triggerBlink, blinkInterval);
  };
  
  onMounted(() => {
    window.addEventListener('mousemove', handleMouseMove);
    scheduleNextBlink(); // Commence à planifier les clignements
  });
  
  onUnmounted(() => {
    window.removeEventListener('mousemove', handleMouseMove);
  });
  </script>
  
  <style scoped>
  .eye-container {
    display: flex;
    justify-content: center;
    align-items: center;
  }
  svg {
    width: 200px;
    height: 100px;
  }
  </style>
  