<template>
    <div class="point-cloud-wrapper">
        <div ref="canvasContainer" class="canvas-container"></div>

        <div v-if="isLoading" class="loading-overlay">
            Processing points...
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as THREE from 'three'

// ----------------------------------------------------------------------
// TYPES
// ----------------------------------------------------------------------

export interface PointData {
    x: number
    y: number
    color: string
    sha1: string
    url: string
    ratio: number
}

interface Props {
    points: PointData[]
    // imagePrefix?: string
    pointSize?: number
    backgroundColor?: number | string
}

const props = withDefaults(defineProps<Props>(), {
    points: () => [],
    // imagePrefix: 'https://via.placeholder.com/128?text=',
    pointSize: 0.15,
    backgroundColor: 0x1a1a1a
})

// ----------------------------------------------------------------------
// STATE (UI / DOM Only)
// ----------------------------------------------------------------------

const canvasContainer = ref<HTMLDivElement | null>(null)
const isLoading = ref(false)
const showPoints = ref(true)
const showImages = ref(true)

// ----------------------------------------------------------------------
// RAW THREE.JS VARIABLES (Non-Reactive for Max Performance)
// ----------------------------------------------------------------------

let scene: THREE.Scene | null = null
let camera: THREE.OrthographicCamera | null = null
let renderer: THREE.WebGLRenderer | null = null
let instancedMesh: THREE.InstancedMesh | null = null
let imageGroup: THREE.Group | null = null

let triggerRender = true

// Data Caches (Raw JS Maps)
const idMap = new Map<string, number>()
const textureCache = new Map<number, THREE.Texture>()

let animationFrameId: number
let resizeObserver: ResizeObserver | null = null
let debounceTimer: ReturnType<typeof setTimeout>

// Mouse Interactivity
let raycaster: THREE.Raycaster = new THREE.Raycaster();
let mouse: THREE.Vector2 = new THREE.Vector2();
let currentlyHoveredPlane: THREE.Mesh | null = null;
const originalZ = 0.01; // Base Z position for all images
const popZ = 0.1;      // Elevated Z position for the hovered image

// ----------------------------------------------------------------------
// LIFECYCLE
// ----------------------------------------------------------------------

onMounted(() => {
    initThree()
    processPoints(props.points)
    animate()

    if (canvasContainer.value) {
        resizeObserver = new ResizeObserver(() => handleResize())
        resizeObserver.observe(canvasContainer.value)
    }
})

onUnmounted(() => {
    if (animationFrameId) cancelAnimationFrame(animationFrameId)
    if (resizeObserver) resizeObserver.disconnect()
    cleanupThree()
})

watch(() => props.points, (newPoints) => {
    processPoints(newPoints)
})

watch(() => props.backgroundColor, (newColor) => {
    if (renderer) renderer.setClearColor(new THREE.Color(newColor))
})

// ----------------------------------------------------------------------
// THREE.JS SETUP
// ----------------------------------------------------------------------

const initThree = () => {
    if (!canvasContainer.value) return

    const width = canvasContainer.value.clientWidth
    const height = canvasContainer.value.clientHeight

    // 1. Scene
    scene = new THREE.Scene()

    // 2. Camera
    const frustumSize = 10
    const aspect = width / height
    camera = new THREE.OrthographicCamera(
        (frustumSize * aspect) / -2,
        (frustumSize * aspect) / 2,
        frustumSize / 2,
        frustumSize / -2,
        0.1,
        1000
    )
    camera.position.z = 10

    // 3. Renderer
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setClearColor(new THREE.Color(props.backgroundColor))

    // Attach to DOM
    canvasContainer.value.appendChild(renderer.domElement)

    // 4. Interaction
    setupInteraction(renderer.domElement, camera)

    // 5. Image Group
    imageGroup = new THREE.Group()
    imageGroup.visible = true // Hidden by default
    scene.add(imageGroup)
}

const cleanupThree = () => {
    if (renderer && canvasContainer.value) {
        canvasContainer.value.removeChild(renderer.domElement)
        renderer.dispose()
    }

    if (instancedMesh) {
        instancedMesh.geometry.dispose()
        if (Array.isArray(instancedMesh.material)) {
            instancedMesh.material.forEach(m => m.dispose())
        } else {
            instancedMesh.material.dispose()
        }
    }

    // Dispose textures to free GPU memory
    textureCache.forEach(t => t.dispose())
    textureCache.clear()
    idMap.clear()

    // Nullify to help GC
    scene = null
    camera = null
    renderer = null
    instancedMesh = null
    imageGroup = null
}

// ----------------------------------------------------------------------
// POINT CLOUD LOGIC
// ----------------------------------------------------------------------

const processPoints = (points: PointData[]) => {
    if (!scene) return
    isLoading.value = true

    // Cleanup old mesh
    if (instancedMesh) {
        scene.remove(instancedMesh)
        instancedMesh.geometry.dispose()
        instancedMesh = null
    }

    idMap.clear()

    if (points.length === 0) {
        isLoading.value = false
        return
    }

    const geometry = new THREE.CircleGeometry(props.pointSize, 32)
    const material = new THREE.MeshBasicMaterial({ color: 0xffffff })
    const mesh = new THREE.InstancedMesh(geometry, material, points.length)

    const tempObj = new THREE.Object3D()
    const tempColor = new THREE.Color()

    for (let i = 0; i < points.length; i++) {
        const p = points[i]
        idMap.set(p.sha1, i)

        tempObj.position.set(p.x, p.y, 0)
        tempObj.updateMatrix()
        mesh.setMatrixAt(i, tempObj.matrix)

        tempColor.set(p.color)
        mesh.setColorAt(i, tempColor)
    }

    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true

    instancedMesh = mesh
    scene.add(mesh)

    // Restore visibility state
    if (showImages.value) {
        updateVisibleImages()
    }

    isLoading.value = false
    updateView()
}

// ----------------------------------------------------------------------
// EXPOSED ACTIONS
// ----------------------------------------------------------------------

const setPointColor = (sha1: string, color: string) => {
    if (!instancedMesh) return

    const index = idMap.get(sha1)
    if (index !== undefined) {
        const c = new THREE.Color(color)
        instancedMesh.setColorAt(index, c)
        if (instancedMesh.instanceColor) {
            instancedMesh.instanceColor.needsUpdate = true
        }
    }
}

const setShowImages = (active: boolean) => {
    showImages.value = active
    if (active) {
        imageGroup.visible = true
        updateVisibleImages()
    } else {
        imageGroup.visible = false
    }
}

const setShowPoints = (active: boolean) => {
    showPoints.value = active
    if (active) {
        instancedMesh.visible = true
        updateVisibleImages()
    } else {
        instancedMesh.visible = false
    }
}

// ----------------------------------------------------------------------
// IMAGE LAZY LOADING (Frustum Culling)
// ----------------------------------------------------------------------

const updateVisibleImages = () => {
    if (!showImages.value || !camera || !imageGroup) return
    const group = imageGroup

    // Clear current planes
    // Optimization: In a real app, use an Object Pool here instead of dispose/new
    while (group.children.length > 0) {
        group.remove(group.children[0])
    }

    // Calc View Bounds
    const zoom = camera.zoom
    const left = (camera.left / zoom) + camera.position.x
    const right = (camera.right / zoom) + camera.position.x
    const top = (camera.top / zoom) + camera.position.y
    const bottom = (camera.bottom / zoom) + camera.position.y

    let imageSize = (1 / zoom) * 10
    imageSize = Math.min(100, imageSize)
    imageSize = Math.max(2, imageSize)


    const loader = new THREE.TextureLoader()
    // console.log("update images", props.points.length)
    // Iterate points
    props.points.forEach((p, index) => {
        const planeGeom = new THREE.PlaneGeometry(props.pointSize * imageSize * p.ratio, props.pointSize * imageSize)
        // Simple AABB check
        if (p.x >= left && p.x <= right && p.y >= bottom && p.y <= top) {

            const material = new THREE.MeshBasicMaterial({
                color: 0xffffff,
                transparent: true
            })

            if (textureCache.has(index)) {
                material.map = textureCache.get(index)!
            } else {
                const url = p.url
                loader.load(
                    url,
                    (tex) => {
                        tex.colorSpace = THREE.SRGBColorSpace
                        textureCache.set(index, tex)
                        material.map = tex
                        material.needsUpdate = true
                        updateView()
                    },
                    undefined,
                    () => material.color.setHex(0xff0000) // Error
                )
            }

            const plane = new THREE.Mesh(planeGeom, material)
            plane.position.set(p.x, p.y, 0)
            group.add(plane)
        }
    })
}

// ----------------------------------------------------------------------
// EVENT HANDLERS
// ----------------------------------------------------------------------

const setupInteraction = (dom: HTMLCanvasElement, cam: THREE.OrthographicCamera) => {
    // --- ZOOM ---
    dom.addEventListener('wheel', (e) => {
        e.preventDefault()
        const zoomSpeed = 0.001 * cam.zoom
        cam.zoom += e.deltaY * -zoomSpeed
        cam.zoom = Math.max(0.01, Math.min(20, cam.zoom))
        cam.updateProjectionMatrix()
        updateView()
        // Use debounce for image update logic (if needed)
        if (showImages.value) debounceImageUpdate()
    }, { passive: false })

    // --- PAN (Updated Logic) ---
    let isDragging = false
    let prevPos = { x: 0, y: 0 }

    // Get the width/height of the canvas in CSS pixels
    const canvasWidth = dom.clientWidth
    const canvasHeight = dom.clientHeight

    dom.addEventListener('mousedown', (e) => {
        isDragging = true
        prevPos = { x: e.clientX, y: e.clientY }
        // Prevent the default cursor behavior (e.g., text selection)
        dom.style.cursor = 'grabbing'
    })

    window.addEventListener('mousemove', (e) => {
        if (!isDragging) return
        const dx = e.clientX - prevPos.x
        const dy = e.clientY - prevPos.y

        // 1. Calculate the current world size visible to the camera.
        // The total width of the view frustum in world units (WorldSize = FrustumSize / Zoom).
        const worldWidth = (cam.right - cam.left) / cam.zoom
        const worldHeight = (cam.top - cam.bottom) / cam.zoom

        // 2. Calculate the World Scale Factor: World Units per Screen Pixel.
        // This is the direct proportion you requested!
        const worldScaleX = worldWidth / canvasWidth
        const worldScaleY = worldHeight / canvasHeight

        // 3. Apply the movement. Mouse drag distance (dx, dy) is converted to world units.
        // dx is inverted because moving the mouse right (positive dx) should move the camera LEFT (negative position change).
        cam.position.x -= dx * worldScaleX
        cam.position.y += dy * worldScaleY // Y axis is typically inverted between screen (top=0) and world (bottom=0)

        prevPos = { x: e.clientX, y: e.clientY }

        updateView()

        if (showImages.value) debounceImageUpdate()
    })

    window.addEventListener('mouseup', () => {
        isDragging = false
        dom.style.cursor = 'grab'
    })

    // Also handle mouse leaving the window
    window.addEventListener('mouseleave', () => {
        isDragging = false
        dom.style.cursor = 'default'
    })

    dom.style.cursor = 'grab'

    renderer.domElement.addEventListener('mousemove', onMouseMove, false);

    function onMouseMove(event: MouseEvent) {
        // Convert mouse position to normalized device coordinates (-1 to +1)
        const rect = renderer!.domElement.getBoundingClientRect();
        mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    }
}

const handleResize = () => {
    if (!canvasContainer.value || !camera || !renderer) return

    const w = canvasContainer.value.clientWidth
    const h = canvasContainer.value.clientHeight
    const aspect = w / h
    const frustumSize = 10

    camera.left = (frustumSize * aspect) / -2
    camera.right = (frustumSize * aspect) / 2
    camera.top = frustumSize / 2
    camera.bottom = frustumSize / -2
    camera.updateProjectionMatrix()

    renderer.setSize(w, h)

    if (showImages.value) updateVisibleImages()
}

const debounceImageUpdate = () => {
    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
        updateVisibleImages()
    }, 100)
}

const animate = () => {
    animationFrameId = requestAnimationFrame(animate)
    if (showImages.value) {
        handleHover();
    }
    // Direct variable access - Fastest possible render loop
    if (renderer && scene && camera && triggerRender) {
        triggerRender = false
        renderer.render(scene, camera)
    }
}

function updateView() {
    triggerRender = true
}

const handleHover = () => {
    if (!camera || !imageGroup || !showImages.value) return;

    raycaster.setFromCamera(mouse, camera);

    // Check intersection with all meshes in the imageGroup
    const intersects = raycaster.intersectObjects(imageGroup.children);

    let newHoveredPlane: THREE.Mesh | null = null;
    let minDistanceSquared = Infinity; // We use squared distance for performance

    if (intersects.length > 0) {
        // Find the intersection whose projected center is closest to the mouse (mouse.x, mouse.y)

        for (const intersect of intersects) {
            const object = intersect.object as THREE.Mesh;

            // 1. Get the object's center in World Coordinates
            const worldPosition = new THREE.Vector3();
            object.getWorldPosition(worldPosition);

            // 2. Project the World Coordinates onto the Screen (Normalized Device Coordinates: -1 to 1)
            // Note: We use the camera's current state to perform the projection
            worldPosition.project(camera);

            // 3. Calculate the 2D distance between the mouse position and the projected center
            const dx = worldPosition.x - mouse.x;
            const dy = worldPosition.y - mouse.y;
            const distanceSquared = dx * dx + dy * dy;

            // 4. Update the closest object
            if (distanceSquared < minDistanceSquared) {
                minDistanceSquared = distanceSquared;
                newHoveredPlane = object;
            }
        }
    }

    if (newHoveredPlane !== currentlyHoveredPlane) {
        // 1. DE-HOVER the old plane
        if (currentlyHoveredPlane) {
            applyHoverEffect(currentlyHoveredPlane, false);
        }

        // 2. HOVER the new plane
        if (newHoveredPlane) {
            applyHoverEffect(newHoveredPlane, true);
        }

        currentlyHoveredPlane = newHoveredPlane;
    }
}

const applyHoverEffect = (plane: THREE.Mesh, isHovering: boolean) => {
    // 1. Z-Position (The "Go Over" effect)
    plane.position.z = isHovering ? popZ : originalZ;

    // 2. Scale (The "Pop Out" effect)
    const scaleFactor = isHovering ? 1.2 : 1.0; // 20% larger on hover
    plane.scale.set(scaleFactor, scaleFactor, 1);

    updateView()
}

// ----------------------------------------------------------------------
// EXPORTS
// ----------------------------------------------------------------------

defineExpose({
    setPointColor,
    setShowImages,
    setShowPoints,
    updatePoints: processPoints
})
</script>

<style scoped>
.point-cloud-wrapper {
    position: relative;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background-color: #1a1a1a;
}

.canvas-container {
    width: 100%;
    height: 100%;
}

.loading-overlay {
    position: absolute;
    bottom: 20px;
    right: 20px;
    padding: 8px 16px;
    background: rgba(0, 0, 0, 0.7);
    color: white;
    border-radius: 4px;
    font-family: sans-serif;
    font-size: 12px;
    pointer-events: none;
}
</style>