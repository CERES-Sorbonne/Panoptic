<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import * as THREE from 'three';

const containerRef = ref(null);

let scene = null;
let camera = null;
let renderer = null;
let points = null;
let animationId = null;

// Orbit controls state
let isDragging = false;
let isPanning = false;
let previousMousePosition = { x: 0, y: 0 };
let cameraRotation = { x: 0, y: 0 };
let cameraDistance = 6;
let panOffset = null;

const updateCameraPosition = () => {
  const x = cameraDistance * Math.sin(cameraRotation.y) * Math.cos(cameraRotation.x);
  const y = cameraDistance * Math.sin(cameraRotation.x);
  const z = cameraDistance * Math.cos(cameraRotation.y) * Math.cos(cameraRotation.x);
  
  camera.position.set(x + panOffset.x, y + panOffset.y, z + panOffset.z);
  camera.lookAt(panOffset);
};

const onMouseDown = (e) => {
  if (e.button === 0) {
    isDragging = true;
  } else if (e.button === 2) {
    isPanning = true;
  }
  previousMousePosition = { x: e.clientX, y: e.clientY };
  e.preventDefault();
};

const onMouseMove = (e) => {
  const deltaX = e.clientX - previousMousePosition.x;
  const deltaY = e.clientY - previousMousePosition.y;

  if (isDragging) {
    cameraRotation.y += deltaX * 0.005;
    cameraRotation.x += deltaY * 0.005;
    
    cameraRotation.x = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, cameraRotation.x));
    
    updateCameraPosition();
  } else if (isPanning) {
    const panSpeed = 0.01;
    const right = new THREE.Vector3();
    const up = new THREE.Vector3();
    
    right.setFromMatrixColumn(camera.matrix, 0);
    up.setFromMatrixColumn(camera.matrix, 1);
    
    panOffset.add(right.multiplyScalar(-deltaX * panSpeed));
    panOffset.add(up.multiplyScalar(deltaY * panSpeed));
    
    updateCameraPosition();
  }

  previousMousePosition = { x: e.clientX, y: e.clientY };
};

const onMouseUp = () => {
  isDragging = false;
  isPanning = false;
};

const onContextMenu = (e) => {
  e.preventDefault();
};

const onWheel = (e) => {
  e.preventDefault();
  cameraDistance += e.deltaY * 0.01;
  cameraDistance = Math.max(1, Math.min(50, cameraDistance));
  updateCameraPosition();
};

const initScene = () => {
  if (!containerRef.value) return;

  // Scene setup
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0a0a);

  // Camera setup
  camera = new THREE.PerspectiveCamera(
    75,
    containerRef.value.clientWidth / containerRef.value.clientHeight,
    0.1,
    1000
  );
  camera.position.z = 5;
  camera.position.y = 2;

  // Initialize pan offset
  panOffset = new THREE.Vector3(0, 0, 0);

  // Renderer setup
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(containerRef.value.clientWidth, containerRef.value.clientHeight);
  containerRef.value.appendChild(renderer.domElement);

  // Generate random point cloud data
  const pointCount = 20000;
  const positions = new Float32Array(pointCount * 3);
  const colors = new Float32Array(pointCount * 3);

  for (let i = 0; i < pointCount; i++) {
    const radius = Math.random() * 20 + 0.5;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);

    positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
    positions[i * 3 + 2] = radius * Math.cos(phi);

    const colorFactor = (positions[i * 3 + 1] + 3) / 6;
    colors[i * 3] = 0.2 + colorFactor * 0.8;
    colors[i * 3 + 1] = 0.5 + Math.random() * 0.3;
    colors[i * 3 + 2] = 0.8 - colorFactor * 0.5;
  }

  // Create point cloud geometry
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  // Create point material
  const material = new THREE.PointsMaterial({
    size: 0.05,
    vertexColors: true,
    transparent: true,
    opacity: 0.8,
    sizeAttenuation: true
  });

  // Create points object
  points = new THREE.Points(geometry, material);
  scene.add(points);

  // Add ambient light
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
  scene.add(ambientLight);

  // Add event listeners
  renderer.domElement.addEventListener('mousedown', onMouseDown);
  renderer.domElement.addEventListener('mousemove', onMouseMove);
  renderer.domElement.addEventListener('mouseup', onMouseUp);
  renderer.domElement.addEventListener('contextmenu', onContextMenu);
  renderer.domElement.addEventListener('wheel', onWheel);

  // Initialize camera position
  updateCameraPosition();
};

const animate = () => {
  animationId = requestAnimationFrame(animate);
  renderer.render(scene, camera);
};

const handleResize = () => {
  if (!containerRef.value || !camera || !renderer) return;
  camera.aspect = containerRef.value.clientWidth / containerRef.value.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(containerRef.value.clientWidth, containerRef.value.clientHeight);
};

onMounted(() => {
  initScene();
  animate();
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  
  if (animationId) {
    cancelAnimationFrame(animationId);
  }
  
  if (renderer && renderer.domElement) {
    renderer.domElement.removeEventListener('mousedown', onMouseDown);
    renderer.domElement.removeEventListener('mousemove', onMouseMove);
    renderer.domElement.removeEventListener('mouseup', onMouseUp);
    renderer.domElement.removeEventListener('contextmenu', onContextMenu);
    renderer.domElement.removeEventListener('wheel', onWheel);
  }
  
  if (points) {
    points.geometry.dispose();
    points.material.dispose();
  }
  
  if (renderer) {
    if (containerRef.value && renderer.domElement) {
      containerRef.value.removeChild(renderer.domElement);
    }
    renderer.dispose();
  }
});
</script>

<template>
  <div class="point-cloud-container">
    <div ref="containerRef" class="canvas-wrapper"></div>
    <div class="info-panel">
      <div class="title">3D Point Cloud Viewer</div>
      <div>Points: 2000</div>
      <div class="controls">
        <div>🖱️ Left Click + Drag: Rotate</div>
        <div>🖱️ Right Click + Drag: Pan</div>
        <div>🖱️ Scroll: Zoom</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.point-cloud-container {
  width: 100%;
  height: 100vh;
  margin: 0;
  padding: 0;
  overflow: hidden;
  position: relative;
}

.canvas-wrapper {
  width: 100%;
  height: 100%;
}

.info-panel {
  position: absolute;
  top: 20px;
  left: 20px;
  color: white;
  font-family: monospace;
  background: rgba(0, 0, 0, 0.7);
  padding: 15px;
  border-radius: 8px;
  font-size: 14px;
  z-index: 10;
}

.title {
  margin-bottom: 8px;
  font-size: 16px;
  font-weight: bold;
}

.controls {
  margin-top: 10px;
  font-size: 12px;
  opacity: 0.8;
}

.controls div {
  margin-bottom: 2px;
}
</style>