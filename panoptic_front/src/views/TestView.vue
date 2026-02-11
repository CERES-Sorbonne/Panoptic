<template>
  <div class="point-cloud-container">
    <div ref="canvasContainer" class="canvas-wrapper"></div>

    <div class="controls">
      <button @click="randomizeColors">Randomize Colors</button>
      <button @click="setRedPoints">Make First 100 Red</button>
      <button @click="setGreenPoints">Make Next 100 Green</button>
      <button @click="toggleAnimation">{{ isAnimating ? 'Stop' : 'Start' }} Color Animation</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as THREE from 'three'

const canvasContainer = ref(null)
const isAnimating = ref(false)

let scene, camera, renderer, points, pointsData
let animationFrameId, colorAnimationInterval
let hue = 0

// ----------------------------- CAMERA ------------------------------
const setupCamera = () => {
  const aspect = window.innerWidth / window.innerHeight
  const frustumSize = 10

  camera = new THREE.OrthographicCamera(
    (frustumSize * aspect) / -2,
    (frustumSize * aspect) / 2,
    frustumSize / 2,
    frustumSize / -2,
    0.1,
    1000
  )
  camera.position.z = 5
}

// ----------------------------- RENDERER ------------------------------
const setupRenderer = () => {
  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(window.innerWidth, window.innerHeight)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setClearColor(0x1a1a1a)
  canvasContainer.value.appendChild(renderer.domElement)
}

// ----------------------------- CONTROLS ------------------------------
const setupControls = () => {
  // Zoom
  renderer.domElement.addEventListener('wheel', e => {
    e.preventDefault()
    const speed = 0.1
    camera.zoom += e.deltaY > 0 ? -speed : speed
    camera.zoom = Math.max(0.5, Math.min(10, camera.zoom))
    camera.updateProjectionMatrix()
  })

  // Pan
  let dragging = false
  let prev = { x: 0, y: 0 }

  renderer.domElement.addEventListener('mousedown', e => {
    dragging = true
    prev = { x: e.clientX, y: e.clientY }
  })

  renderer.domElement.addEventListener('mousemove', e => {
    if (!dragging) return
    const dx = e.clientX - prev.x
    const dy = e.clientY - prev.y

    const speed = 0.01 / camera.zoom
    camera.position.x -= dx * speed
    camera.position.y += dy * speed
    prev = { x: e.clientX, y: e.clientY }
  })

  renderer.domElement.addEventListener('mouseup', () => (dragging = false))
  renderer.domElement.addEventListener('mouseleave', () => (dragging = false))

  const raycaster = new THREE.Raycaster()
  const mouse = new THREE.Vector2()

  renderer.domElement.addEventListener('click', onClick)

  function onClick(event) {
    // Convert mouse position to normalized device coordinates (-1 to +1)
    const rect = renderer.domElement.getBoundingClientRect()
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

    raycaster.setFromCamera(mouse, camera)

    // Check intersection with the instanced mesh
    const intersects = raycaster.intersectObject(points) // 'points' is your InstancedMesh
    if (intersects.length > 0) {
      const instanceId = intersects[intersects.length-1].instanceId
      if (instanceId !== undefined) {
        changeInstanceColor(instanceId)
      }
    }
  }
}

function changeInstanceColor(id) {
  const newColor = new THREE.Color(Math.random(), Math.random(), Math.random())
  points.setColorAt(id, newColor)
  points.instanceColor.needsUpdate = true
}


// ----------------------------- RESIZE ------------------------------
const handleResize = () => {
  const aspect = window.innerWidth / window.innerHeight
  const frustumSize = 10

  camera.left = (frustumSize * aspect) / -2
  camera.right = (frustumSize * aspect) / 2
  camera.top = frustumSize / 2
  camera.bottom = frustumSize / -2
  camera.updateProjectionMatrix()

  renderer.setSize(window.innerWidth, window.innerHeight)
}

// ----------------------------- CREATE POINTS ------------------------------
const setPoints = pointsArray => {
  if (points) {
    scene.remove(points)
    points.geometry.dispose()
    points.material.dispose()
  }

  pointsData = pointsArray

  const geom = new THREE.CircleGeometry(0.15, 32)

  // THIS is the important part ⬇⬇⬇
  const mat = new THREE.MeshBasicMaterial({ color: 0xffffff }) // ✅ USE THIS (White base)

  const mesh = new THREE.InstancedMesh(geom, mat, pointsArray.length)

  const tmpColor = new THREE.Color()
  const tmpObj = new THREE.Object3D()

  for (let i = 0; i < pointsArray.length; i++) {
    const p = pointsArray[i]

    // position
    tmpObj.position.set(p.x, p.y, 0)
    tmpObj.updateMatrix()
    mesh.setMatrixAt(i, tmpObj.matrix)

    // color
    const c = p.color || { r: 1, g: 1, b: 1 }
    tmpColor.setRGB(c.r, c.g, c.b)
    mesh.setColorAt(i, tmpColor)
  }

  mesh.instanceMatrix.needsUpdate = true
  mesh.instanceColor.needsUpdate = true

  points = mesh
  scene.add(points)
}


// ----------------------------- COLOR UPDATES ------------------------------
const setPointColor = (index, r, g, b) => {
  if (!points || index < 0 || index >= points.count) return

  const c = new THREE.Color(r, g, b)
  points.setColorAt(index, c)
  points.instanceColor.needsUpdate = true
}

const setPointColors = updates => {
  if (!points) return
  const color = new THREE.Color()

  updates.forEach(({ index, r, g, b }) => {
    if (index < 0 || index >= points.count) return
    color.setRGB(r, g, b)
    points.setColorAt(index, color)
  })

  points.instanceColor.needsUpdate = true
}

const setAllPointsColor = (r, g, b) => {
  if (!points) return
  const c = new THREE.Color(r, g, b)

  for (let i = 0; i < points.count; i++) {
    points.setColorAt(i, c)
  }

  points.instanceColor.needsUpdate = true
}

// ----------------------------- ANIMATION LOOP ------------------------------
const animate = () => {
  animationFrameId = requestAnimationFrame(animate)
  renderer.render(scene, camera)
}

// ----------------------------- BUTTON ACTIONS ------------------------------
const randomizeColors = () => {
  for (let i = 0; i < pointsData.length; i++) {
    setPointColor(i, Math.random(), Math.random(), Math.random())
  }
}

const setRedPoints = () => {
  for (let i = 0; i < Math.min(100, pointsData.length); i++) {
    setPointColor(i, 1, 0, 0)
  }
}

const setGreenPoints = () => {
  const arr = []
  for (let i = 100; i < Math.min(200, pointsData.length); i++) {
    arr.push({ index: i, r: 0, g: 1, b: 0 })
  }
  setPointColors(arr)
}

const toggleAnimation = () => {
  isAnimating.value = !isAnimating.value

  if (isAnimating.value) {
    colorAnimationInterval = setInterval(() => {
      hue = (hue + 1) % 360
      const h = hue / 360

      const s = 1
      const l = 0.5
      const c = (1 - Math.abs(2 * l - 1)) * s
      const x = c * (1 - Math.abs(((h * 6) % 2) - 1))
      const m = l - c / 2

      let r, g, b
      if (h < 1 / 6) { r = c; g = x; b = 0 }
      else if (h < 2 / 6) { r = x; g = c; b = 0 }
      else if (h < 3 / 6) { r = 0; g = c; b = x }
      else if (h < 4 / 6) { r = 0; g = x; b = c }
      else if (h < 5 / 6) { r = x; g = 0; b = c }
      else { r = c; g = 0; b = x }

      for (let i = 200; i < Math.min(300, pointsData.length); i++) {
        setPointColor(i, r + m, g + m, b + m)
      }
    }, 50)
  } else {
    clearInterval(colorAnimationInterval)
  }
}

// ----------------------------- MOUNT ------------------------------
onMounted(() => {
  scene = new THREE.Scene()
  setupCamera()
  setupRenderer()
  setupControls()

  // Generate random points with random colors
  const pts = []
  for (let i = 0; i < 100; i++) {
    pts.push({
      x: (Math.random() - 0.5) * 8,
      y: (Math.random() - 0.5) * 8,
      color: {
        r: Math.random(),
        g: Math.random(),
        b: Math.random()
      }
    })
  }


  setPoints(pts)
  animate()

  window.addEventListener('resize', handleResize)
})

// ----------------------------- UNMOUNT ------------------------------
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)

  if (animationFrameId) cancelAnimationFrame(animationFrameId)
  if (colorAnimationInterval) clearInterval(colorAnimationInterval)

  if (points) {
    points.geometry.dispose()
    points.material.dispose()
  }

  if (renderer) renderer.dispose()
})

// Expose functions
defineExpose({ setPointColor, setPointColors, setAllPointsColor })
</script>

<style scoped>
.point-cloud-container {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  position: relative;
}

.canvas-wrapper {
  width: 100%;
  height: 100%;
}

.controls {
  position: absolute;
  top: 20px;
  left: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  z-index: 10;
}

button {
  padding: 10px 20px;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.3s;
}

button:hover {
  background-color: #45a049;
}

button:active {
  background-color: #3d8b40;
}
</style>
