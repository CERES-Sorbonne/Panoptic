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
import KDBush from 'kdbush'
import { useDataStore } from '@/data/dataStore'

const data = useDataStore()

// ----------------------------------------------------------------------
// TYPES
// ----------------------------------------------------------------------

export interface PointData {
    x: number
    y: number
    color: string
    sha1: string
    ratio: number,
    id?: number
}

interface Props {
    points: PointData[]
    // imagePrefix?: string
    pointSize?: number
    backgroundColor?: number | string
    showImages: boolean
    showPoints: boolean

    baseImageSize: number
    maxImageSize: number
    minImageSize: number
}

const props = withDefaults(defineProps<Props>(), {
    points: () => [],
    // imagePrefix: 'https://via.placeholder.com/128?text=',
    pointSize: 0.10,
    backgroundColor: 0x1a1a1a,

    baseImageSize: 5,
    maxImageSize: 200,
    minImageSize: 20
})

// ----------------------------------------------------------------------
// STATE (UI / DOM Only)
// ----------------------------------------------------------------------

const canvasContainer = ref<HTMLDivElement | null>(null)
const isLoading = ref(false)

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
const textureCache = {
    small: new Map<number, THREE.Texture>(),
    raw: new Map<number, THREE.Texture>()
}
// FIX: Tracking pending requests to prevent network flooding
const pendingTextures = {
    small: new Set<number>(),
    raw: new Set<number>()
}
let animationFrameId: number
let resizeObserver: ResizeObserver | null = null
let debounceTimer: ReturnType<typeof setTimeout>

const sharedPlaneGeo = new THREE.PlaneGeometry(1, 1)
const textureLoader = new THREE.TextureLoader() // FIX: Reusable loader instance

// Mouse Interactivity
let raycaster: THREE.Raycaster = new THREE.Raycaster();
let mouse: THREE.Vector2 = new THREE.Vector2();
let ignore_hover_once = false
const hoveredPointId = ref<number | null>(null) // Track which point is hovered
const originalZ = 0.01; // Base Z position for all images
const popZ = 0.1;      // Elevated Z position for the hovered image

// KDtree
let tree: KDBush = null // KDTree for optimal point query
let treeToPointMap: Map<number, PointData> = new Map()

// ----------------------------------------------------------------------
// LIFECYCLE
// ----------------------------------------------------------------------

onMounted(() => {
    initThree()
    processPoints()
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
    processPoints()
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
    Object.values(textureCache).forEach(t => t.forEach(tc => tc.dispose()))
    Object.values(textureCache).forEach(t => t.clear())
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

const processPoints = () => {
    if (!scene) return
    isLoading.value = true

    const points = props.points

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

    createKDTree(points)

    // Restore visibility state
    if (props.showImages) {
        updateVisibleImages()
    }

    isLoading.value = false
    updateView()
}

function createKDTree(points: PointData[]) {
    treeToPointMap = new Map()
    tree = new KDBush(points.length)
    for (let point of points) {
        const id = tree.add(point.x, point.y)
        treeToPointMap.set(id, point)
        point.id = id
    }
    tree.finish()
}

function getPointsInRect(minX, minY, maxX, maxY) {
    const ids = tree.range(minX, minY, maxX, maxY)
    return ids.map(id => treeToPointMap.get(id))
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



const updateShowImages = (active: boolean) => {
    if (active) {
        imageGroup.visible = true
        updateVisibleImages()
    } else {
        imageGroup.visible = false
    }
}

const updateShowPoints = (active: boolean) => {
    if (active) {
        instancedMesh.visible = true
        updateVisibleImages()
    } else {
        instancedMesh.visible = false
    }
}

watch(() => props.showImages, updateShowImages)
watch(() => props.showPoints, updateShowPoints)

// ----------------------------------------------------------------------
// IMAGE LAZY LOADING (Frustum Culling)
// ----------------------------------------------------------------------

const getAdaptiveWorldSize = (baseSize, zoom) => {
    const k = 0.5 
    let targetVisualSize = baseSize * Math.pow(zoom, k)

    const minPixelSize = props.minImageSize // Use props
    const maxPixelSize = props.maxImageSize // Use props
    targetVisualSize = Math.max(minPixelSize, Math.min(targetVisualSize, maxPixelSize))

    return targetVisualSize / zoom
}

const getTexture = (quality, point) => {
    // 1. Check if loaded
    if (textureCache[quality].has(point.id)) {
        return textureCache[quality].get(point.id)
    }
    
    // 2. Check if already loading (FIX: prevents network flooding)
    if (pendingTextures[quality].has(point.id)) {
        // Fallback: If 'raw' is pending, use 'small' if available
        if (quality === 'raw' && textureCache['small'].has(point.id)) {
            return textureCache['small'].get(point.id)
        }
        return null 
    }
    
    // 3. Start Load
    pendingTextures[quality].add(point.id)
    const url = data.baseImgUrl + quality + '/' + point.sha1
    
    textureLoader.load( // Use the reusable textureLoader instance
        url,
        (tex) => {
            tex.colorSpace = THREE.SRGBColorSpace
            textureCache[quality].set(point.id, tex)
            pendingTextures[quality].delete(point.id)
            
            // FIX: Rebuild the scene to add the mesh with the new texture
            debounceImageUpdate() 
        },
        undefined,
        (err) => {
            console.error('Texture loading failed:', err)
            pendingTextures[quality].delete(point.id)
            debounceImageUpdate() // Rebuild to remove placeholder/handle error state
        }
    )
    
    // 4. Fallback while loading
    if (quality === 'raw' && textureCache['small'].has(point.id)) {
        return textureCache['small'].get(point.id)
    }
    return null // Return null if not cached and not loading, or if small is also missing
}

const updateVisibleImages = () => {
    if (!props.showImages || !camera || !imageGroup || !props.points.length) return

    imageGroup.children.forEach((object) => {
        if (object instanceof THREE.Mesh) {
            if (Array.isArray(object.material)) {
                object.material.forEach(m => m.dispose())
            } else {
                object.material.dispose()
            }
        }
    })

    imageGroup.clear() 
    
    ignore_hover_once = true
    
    // 2. Calculate View Bounds
    const zoom = camera.zoom
    const left = (camera.left / zoom) + camera.position.x
    const right = (camera.right / zoom) + camera.position.x
    const top = (camera.top / zoom) + camera.position.y
    const bottom = (camera.bottom / zoom) + camera.position.y

    // 3. Grid / Culling Logic
    let imgQuality = 'small'
    if (zoom > 5) imgQuality = 'raw'

    const gridSize = getGridStepSize(zoom) * 1.5
    let visiblePoints = getPointsInRect(left - gridSize, bottom - gridSize, right + gridSize, top + gridSize)
    
    if (gridSize > 1.25) {
        visiblePoints = selectImagesForGrid(visiblePoints, gridSize)
    }

    // 4. Calculate Shared Size
    const worldSize = getAdaptiveWorldSize(props.baseImageSize, zoom)

    // 5. Render
    visiblePoints.forEach((p) => {
        const isHovered = hoveredPointId.value === p.id
        const scaleFactor = isHovered ? 2 : 1
        const zPosition = isHovered ? popZ : originalZ

        let quality = (isHovered || imgQuality === 'raw') ? 'raw' : 'small'

        const texture = getTexture(quality, p)

        // FIX: Only render the plane if the texture is ready
        if (!texture) return 

        const finalWidth = 0.05 * worldSize * p.ratio * scaleFactor
        const finalHeight = 0.05 * worldSize * scaleFactor
        
        // Material is now only created when texture is available
        const material = new THREE.MeshBasicMaterial({
            map: texture,
            color: 0xffffff,
            transparent: true
        })

        const plane = new THREE.Mesh(sharedPlaneGeo, material)
        
        plane.scale.set(finalWidth, finalHeight, 1)
        plane.position.set(p.x, p.y, zPosition)
        plane.userData.pointId = p.id
        
        if (isHovered) plane.renderOrder = 999 

        imageGroup!.add(plane)
    })

    // CRITICAL FIX: Trigger render after all meshes are added/updated
    updateView() 
}

watch(props, () => {
    // Changing the size requires rebuilding the meshes
    updateVisibleImages()
})

// ----------------------------------------------------------------------
// EVENT HANDLERS
// ----------------------------------------------------------------------
const setupInteraction = (dom: HTMLCanvasElement, cam: THREE.OrthographicCamera) => {
    // --- ZOOM with Pan-to-Mouse ---
    dom.addEventListener('wheel', (e) => {
        e.preventDefault()
        
        // Get mouse position in normalized device coordinates (-1 to +1)
        const rect = dom.getBoundingClientRect()
        const mouseX = ((e.clientX - rect.left) / rect.width) * 2 - 1
        const mouseY = -((e.clientY - rect.top) / rect.height) * 2 + 1
        
        // Convert mouse position to world coordinates BEFORE zoom
        const worldWidth = (cam.right - cam.left) / cam.zoom
        const worldHeight = (cam.top - cam.bottom) / cam.zoom
        const mouseWorldX = cam.position.x + mouseX * worldWidth / 2
        const mouseWorldY = cam.position.y + mouseY * worldHeight / 2
        
        // Apply zoom
        const oldZoom = cam.zoom
        const zoomSpeed = 0.001 * cam.zoom
        cam.zoom += e.deltaY * -zoomSpeed
        cam.zoom = Math.max(0.01, Math.min(20, cam.zoom))
        
        // Calculate new world dimensions after zoom
        const newWorldWidth = (cam.right - cam.left) / cam.zoom
        const newWorldHeight = (cam.top - cam.bottom) / cam.zoom
        
        // Calculate where the mouse now points in world coordinates
        const newMouseWorldX = cam.position.x + mouseX * newWorldWidth / 2
        const newMouseWorldY = cam.position.y + mouseY * newWorldHeight / 2
        
        // Adjust camera position so mouse stays over the same world point
        cam.position.x += mouseWorldX - newMouseWorldX
        cam.position.y += mouseWorldY - newMouseWorldY
        
        cam.updateProjectionMatrix()
        updateView()
        
        // Use debounce for image update logic (if needed)
        if (props.showImages) debounceImageUpdate()
    }, { passive: false })

    // --- PAN ---
    let isDragging = false
    let prevPos = { x: 0, y: 0 }

    const canvasWidth = dom.clientWidth
    const canvasHeight = dom.clientHeight

    dom.addEventListener('mousedown', (e) => {
        isDragging = true
        prevPos = { x: e.clientX, y: e.clientY }
        dom.style.cursor = 'grabbing'
        updateView()
    })

    window.addEventListener('mousemove', (e) => {
        if (!isDragging) return
        const dx = e.clientX - prevPos.x
        const dy = e.clientY - prevPos.y

        const worldWidth = (cam.right - cam.left) / cam.zoom
        const worldHeight = (cam.top - cam.bottom) / cam.zoom

        const worldScaleX = worldWidth / canvasWidth
        const worldScaleY = worldHeight / canvasHeight

        cam.position.x -= dx * worldScaleX
        cam.position.y += dy * worldScaleY

        prevPos = { x: e.clientX, y: e.clientY }
        cam.updateProjectionMatrix()
        updateView()

        if (props.showImages) debounceImageUpdate()
    })

    window.addEventListener('mouseup', () => {
        isDragging = false
        dom.style.cursor = 'grab'
        cam.updateProjectionMatrix()
        updateView()

        if (props.showImages) debounceImageUpdate()
    })

    window.addEventListener('mouseleave', () => {
        isDragging = false
        dom.style.cursor = 'default'
    })

    dom.style.cursor = 'grab'

    renderer.domElement.addEventListener('mousemove', onMouseMove, false)

    function onMouseMove(event: MouseEvent) {
        const rect = renderer!.domElement.getBoundingClientRect()
        mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
        mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
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

    if (props.showImages) updateVisibleImages()
}

const debounceImageUpdate = () => {
    // no debounce for now as it seems to make it bug.
    updateVisibleImages()
    // updateView()
}

const animate = () => {
    animationFrameId = requestAnimationFrame(animate)
    if (props.showImages) {
        handleHover();
    }

    if (renderer && scene && camera && triggerRender) {
        triggerRender = false
        renderer.render(scene, camera)
    }
}

function updateView() {
    triggerRender = true
}

const handleHover = () => {
    if (!camera || !imageGroup || !props.showImages) return
    if(ignore_hover_once) {
        ignore_hover_once = false
        return
    }

    raycaster.setFromCamera(mouse, camera)

    // Check intersection with all meshes in the imageGroup
    const intersects = raycaster.intersectObjects(imageGroup.children)

    let newHoveredPointId: number | null = null
    let minDistanceSquared = Infinity

    if (intersects.length > 0) {
        // Find the intersection whose projected center is closest to the mouse
        for (const intersect of intersects) {
            const object = intersect.object as THREE.Mesh

            // Get the object's center in World Coordinates
            const worldPosition = new THREE.Vector3()
            object.getWorldPosition(worldPosition)

            // Project the World Coordinates onto the Screen
            worldPosition.project(camera)

            // Calculate the 2D distance between the mouse position and the projected center
            const dx = worldPosition.x - mouse.x
            const dy = worldPosition.y - mouse.y
            const distanceSquared = dx * dx + dy * dy

            // Update the closest object
            if (distanceSquared < minDistanceSquared) {
                minDistanceSquared = distanceSquared
                newHoveredPointId = object.userData.pointId
            }
        }
    }

    // If hovered point changed, rebuild the images
    if (newHoveredPointId !== hoveredPointId.value) {
        hoveredPointId.value = newHoveredPointId
        updateVisibleImages()
        updateView()
    }

    // console.log(newHoveredPointId)
}

// grid utils

/**
 * Calculate the current grid step size based on zoom level.
 * Grid size doubles at each level, ensuring grid lines always align.
 * 
 * @param zoom - Current camera zoom level
 * @param baseGridSize - Base grid size at zoom = 1 (default: 1.0)
 * @param zoomThresholds - Zoom levels where grid doubles (default: [0.5, 1, 2, 4, 8, 16])
 * @returns The grid step size for current zoom
 */
function getGridStepSize(
    zoom: number,
    baseGridSize: number = 5.0,
    zoomThresholds: number[] = [0.25, 0.5, 1, 2, 4, 8, 16, 32]
): number {
    // Find which threshold we're above
    // Higher zoom = more zoomed in = smaller grid cells
    // Lower zoom = more zoomed out = larger grid cells

    for (let i = zoomThresholds.length - 1; i >= 0; i--) {
        if (zoom >= zoomThresholds[i]) {
            // At this zoom level, divide base size by 2^i
            return baseGridSize / Math.pow(2, i)
        }
    }

    // If zoom is below minimum threshold, use largest grid
    return baseGridSize * 2
}

/**
 * Select one image per grid cell - the one closest to the cell's center.
 * 
 * @param points - All points to consider
 * @param gridStepSize - Size of each grid cell (from getGridStepSize)
 * @returns Array of selected points (one per occupied grid cell)
 */
function selectImagesForGrid(
    points: PointData[],
    gridStepSize: number
): PointData[] {
    // Map to store best point per grid cell
    // Key: "cellX,cellY", Value: { point, distanceSquared }
    const gridCells = new Map<string, { point: PointData; distSq: number }>()

    for (const point of points) {
        // Determine which grid cell this point belongs to
        const cellX = Math.floor(point.x / gridStepSize)
        const cellY = Math.floor(point.y / gridStepSize)
        const cellKey = `${cellX},${cellY}`

        // Calculate upper-left corner of this grid cell (grid origin point)
        const gridPointX = cellX * gridStepSize
        const gridPointY = (cellY + 1) * gridStepSize  // +1 because "upper" means higher Y

        // Calculate squared distance to grid corner (avoid sqrt for performance)
        const dx = point.x - gridPointX
        const dy = point.y - gridPointY
        const distSq = dx * dx + dy * dy

        // Check if this point is closer to grid corner than current best
        const existing = gridCells.get(cellKey)
        if (!existing || distSq < existing.distSq) {
            gridCells.set(cellKey, { point, distSq })
        }
    }

    // Extract just the points
    return Array.from(gridCells.values()).map(entry => entry.point)
}

// ----------------------------------------------------------------------
// EXPORTS
// ----------------------------------------------------------------------

defineExpose({
    setPointColor,
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