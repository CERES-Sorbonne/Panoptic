// useMapLogic.ts (Refactored)
import { ref, watch, type Ref } from 'vue' // Removed watch if unused
import * as THREE from 'three'
import KDBush from 'kdbush'
import { Props } from '@/components/mapview/ImageMap.vue'
import { CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import { usePointLogic } from './usePointLogic'
import { useImageLogic } from './useImageLogic'
import { useBoxLogic } from './useBoxLogic'
import { useLassoLogic } from './useLassoLogic' // NEW IMPORT

// --- Types (Same as before) ---
export interface BoundingBox {
    minX: number
    minY: number
    maxX: number
    maxY: number
    color?: string
    label?: string
}

export interface PointData {
    x: number
    y: number
    color: string
    sha1: string
    ratio: number,
    id?: number,
    border?: boolean
}

interface PointCloudVizParams {
    dataStore: any
    isLoadingRef: Ref<boolean>
    props: Props
    lassoCalback
}

// ----------------------------------------------------------------------
// GLOBAL / CONSTANT VARIABLES
// ----------------------------------------------------------------------

let scene: THREE.Scene | null = null
let camera: THREE.OrthographicCamera | null = null
let renderer: THREE.WebGLRenderer | null = null
let labelRenderer: CSS2DRenderer | null = null

let animationFrameId: number

// Data Caches
const idMap = new Map<string, number>()
const treeToPointMap: Map<number, PointData> = new Map()

// Mouse Interactivity
let raycaster: THREE.Raycaster = new THREE.Raycaster();
let mouse: THREE.Vector2 = new THREE.Vector2();
let ignore_hover_once = false
const hoveredPointId = ref<number | null>(null)

// KDtree
const tree: { t: KDBush | null } = { t: null }

// Rendering State
let triggerRender = true
let resizeObserver: ResizeObserver | null = null
let dataStore: any

// Module Hooks
let pointLogic: ReturnType<typeof usePointLogic> | null = null
let imageLogic: ReturnType<typeof useImageLogic> | null = null
let boxLogic: ReturnType<typeof useBoxLogic> | null = null
let lassoLogic: ReturnType<typeof useLassoLogic> | null = null // NEW HOOK

// ----------------------------------------------------------------------
// CORE COMPOSABLE
// ----------------------------------------------------------------------

export function useMapLogic({ dataStore: store, isLoadingRef, props, lassoCalback }: PointCloudVizParams) {
    dataStore = store

    // --- Utility Functions ---

    function updateView() {
        triggerRender = true
    }

    const animate = () => {
        animationFrameId = requestAnimationFrame(animate)
        if (props.showImages && camera && imageLogic) {
            handleHover();
            imageLogic.updateAnimations();
        }

        if (renderer && scene && camera && triggerRender) {
            triggerRender = false
            renderer.render(scene, camera)
            if (labelRenderer) {
                labelRenderer.render(scene, camera)
            }
        }
    }

    // --- THREE.JS SETUP ---

    const init = (domElement: HTMLDivElement) => {
        const width = domElement.clientWidth
        const height = domElement.clientHeight

        // 1. Scene
        scene = new THREE.Scene()

        // 2. Camera (Orthographic)
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
        camera.zoom = 0.08
        camera.updateProjectionMatrix()


        // 3. Renderers
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
        renderer.setSize(width, height)
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
        renderer.setClearColor(new THREE.Color(props.backgroundColor))
        domElement.appendChild(renderer.domElement)

        labelRenderer = new CSS2DRenderer()
        labelRenderer.setSize(width, height)
        labelRenderer.domElement.style.position = 'absolute'
        labelRenderer.domElement.style.top = '0px'
        labelRenderer.domElement.style.pointerEvents = 'none'
        domElement.appendChild(labelRenderer.domElement)

        // 4. Initialize Logic Modules
        if (scene && camera && labelRenderer) {
            pointLogic = usePointLogic({ scene, props, isLoadingRef, idMap, updateView })
            imageLogic = useImageLogic({ scene, camera, props, dataStore, tree, treeToPointMap, hoveredPointId, updateView, renderer })
            boxLogic = useBoxLogic({ scene, camera, props, labelRenderer, updateView })
            lassoLogic = useLassoLogic({ scene, props, tree, updateView, onLassoComplete: lassoCalback }) // NEW INIT

            imageLogic.initImageGroup()
        }

        // 5. Interaction
        setupInteraction(renderer.domElement, camera!)

        // 6. Start animation loop
        animate()

        // 7. Resize Observer
        resizeObserver = new ResizeObserver(() => handleResize(domElement))
        resizeObserver.observe(domElement)
    }

    const cleanup = () => {
        if (animationFrameId) cancelAnimationFrame(animationFrameId)
        if (resizeObserver) resizeObserver.disconnect()

        if (renderer && renderer.domElement.parentNode) {
            renderer.domElement.parentNode.removeChild(renderer.domElement)
            renderer.dispose()
        }
        if (labelRenderer && labelRenderer.domElement.parentNode) {
            labelRenderer.domElement.parentNode.removeChild(labelRenderer.domElement)
        }

        if (imageLogic) imageLogic.disposeTextures()
        if (boxLogic) boxLogic.cleanupBoxes()
        if (lassoLogic) lassoLogic.cleanup() // NEW CLEANUP

        idMap.clear()
        treeToPointMap.clear()

        scene = null
        camera = null
        renderer = null
        labelRenderer = null
        tree.t = null
        pointLogic = null
        imageLogic = null
        boxLogic = null
        lassoLogic = null
    }

    // --- Data Processing (Same as before) ---
    function createKDTree(points: PointData[]) {
        treeToPointMap.clear()
        tree.t = new KDBush(points.length)
        for (let point of points) {
            const id = tree.t.add(point.x, point.y)
            treeToPointMap.set(id, point)
            point.id = id
        }
        tree.t.finish()
    }

    function processPoints(points: PointData[]) {
        if (!pointLogic || !imageLogic) return
        pointLogic.processPoints(points)
        createKDTree(points)
        imageLogic.updateVisibleImages()
    }

    // --- INTERACTION / RESIZE ---

    const handleResize = (domElement: HTMLDivElement) => {
        if (!camera || !renderer) return
        const w = domElement.clientWidth
        const h = domElement.clientHeight
        const aspect = w / h
        const frustumSize = 10
        camera.left = (frustumSize * aspect) / -2
        camera.right = (frustumSize * aspect) / 2
        camera.top = frustumSize / 2
        camera.bottom = frustumSize / -2
        camera.updateProjectionMatrix()
        renderer.setSize(w, h)
        if (labelRenderer) labelRenderer.setSize(w, h)
        if (props.showImages && imageLogic) imageLogic.updateVisibleImages()
        if (boxLogic) boxLogic.updateBoundingBoxesOnZoom()
        updateView()
    }

    const handleHover = () => {
        // Skip hover effects if we are drawing a lasso
        if (props.mouseMode.startsWith('lasso')) return;

        if (!camera || !imageLogic || !props.showImages) return
        if (ignore_hover_once) {
            ignore_hover_once = false
            return
        }

        const imageGroup = imageLogic.getImageGroup()
        if (!imageGroup) return
        raycaster.setFromCamera(mouse, camera)
        const intersects = raycaster.intersectObjects(imageGroup.children)
        let newHoveredPointId: number | null = null
        let minDistanceSquared = Infinity
        if (intersects.length > 0) {
            for (const intersect of intersects) {
                const object = intersect.object as THREE.Mesh
                const worldPosition = new THREE.Vector3()
                object.getWorldPosition(worldPosition)
                worldPosition.project(camera)
                const dx = worldPosition.x - mouse.x
                const dy = worldPosition.y - mouse.y
                const distanceSquared = dx * dx + dy * dy
                if (distanceSquared < minDistanceSquared) {
                    minDistanceSquared = distanceSquared
                    newHoveredPointId = object.userData.pointId
                }
            }
        }
        if (newHoveredPointId !== hoveredPointId.value) {
            hoveredPointId.value = newHoveredPointId
            imageLogic.updateVisibleImages()
            updateView()
        }
    }

    /**
     * Helper to get World Coordinates from Mouse Event
     */
    const getWorldPosition = (e: MouseEvent, cam: THREE.OrthographicCamera, dom: HTMLCanvasElement): THREE.Vector3 => {
        const rect = dom.getBoundingClientRect()
        const mouseX = ((e.clientX - rect.left) / rect.width) * 2 - 1
        const mouseY = -((e.clientY - rect.top) / rect.height) * 2 + 1

        // Unproject the mouse coordinates to get a point in 3D space
        // We set Z to 0 because our map is on the Z=0 plane
        const vec = new THREE.Vector3(mouseX, mouseY, 0)
        vec.unproject(cam)
        vec.z = 0 // Enforce Z=0 flatness
        return vec
    }

    const setupInteraction = (dom: HTMLCanvasElement, cam: THREE.OrthographicCamera) => {
        // --- ZOOM with Pan-to-Mouse (Same as before) ---
        dom.addEventListener('wheel', (e) => {
            e.preventDefault()
            const rect = dom.getBoundingClientRect()
            const mouseX = ((e.clientX - rect.left) / rect.width) * 2 - 1
            const mouseY = -((e.clientY - rect.top) / rect.height) * 2 + 1
            const worldWidth = (cam.right - cam.left) / cam.zoom
            const worldHeight = (cam.top - cam.bottom) / cam.zoom
            const mouseWorldX = cam.position.x + mouseX * worldWidth / 2
            const mouseWorldY = cam.position.y + mouseY * worldHeight / 2
            const zoomSpeed = 0.001 * cam.zoom
            cam.zoom += e.deltaY * -zoomSpeed
            cam.zoom = Math.max(0.01, Math.min(20, cam.zoom))
            const newWorldWidth = (cam.right - cam.left) / cam.zoom
            const newWorldHeight = (cam.top - cam.bottom) / cam.zoom
            const newMouseWorldX = cam.position.x + mouseX * newWorldWidth / 2
            const newMouseWorldY = cam.position.y + mouseY * newWorldHeight / 2
            cam.position.x += mouseWorldX - newMouseWorldX
            cam.position.y += mouseWorldY - newMouseWorldY
            cam.updateProjectionMatrix()
            if (boxLogic) boxLogic.updateBoundingBoxesOnZoom()
            updateView()
            if (props.showImages && imageLogic) imageLogic.updateVisibleImages()
        }, { passive: false })

        // --- INTERACTION LOGIC ---
        let isDragging = false
        let isLassoing = false // Track lasso state
        let prevPos = { x: 0, y: 0 }
        const canvasWidth = dom.clientWidth
        const canvasHeight = dom.clientHeight

        dom.addEventListener('mousedown', (e) => {
            // Check for Lasso Mode
            if (props.mouseMode.startsWith('lasso')) {
                isLassoing = true
                const worldPos = getWorldPosition(e, cam, dom)

                // PASS SCREEN COORDS
                lassoLogic?.start(worldPos, { x: e.clientX, y: e.clientY })

                return
            }

            // Check for Pan Mode
            if (props.mouseMode === 'pan') {
                isDragging = true
                prevPos = { x: e.clientX, y: e.clientY }
                dom.style.cursor = 'grabbing'
                updateView()
            }
        })

        window.addEventListener('mousemove', (e) => {
            // HANDLE LASSO
            if (isLassoing && props.mouseMode.startsWith('lasso')) {
                const worldPos = getWorldPosition(e, cam, dom)

                // PASS SCREEN COORDS
                lassoLogic?.move(worldPos, { x: e.clientX, y: e.clientY })

                return
            }

            // HANDLE PAN
            if (isDragging && props.mouseMode === 'pan') {
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
                if (props.showImages && imageLogic) imageLogic.updateVisibleImages()
            }
        })

        window.addEventListener('mouseup', () => {
            // END LASSO
            if (isLassoing) {
                isLassoing = false
                lassoLogic?.end()
                return
            }

            // END PAN
            if (isDragging) {
                isDragging = false
                dom.style.cursor = 'inherit'
                cam.updateProjectionMatrix()
                updateView()
                if (props.showImages && imageLogic) imageLogic.updateVisibleImages()
            }
        })

        window.addEventListener('mouseleave', () => {
            isDragging = false
            if (isLassoing) {
                isLassoing = false
                lassoLogic?.end() // Auto-finish lasso on leave
            }
            dom.style.cursor = 'inherit'
        })

        dom.style.cursor = 'inherit'

        // Standard mouse move tracking for Hover effects
        renderer!.domElement.addEventListener('mousemove', onMouseMove, false)

        function onMouseMove(event: MouseEvent) {
            const rect = renderer!.domElement.getBoundingClientRect()
            mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
            mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
        }
    }

    return {
        init,
        cleanup,
        processPoints,
        updateView,
        updateShowPoints: (active: boolean) => pointLogic?.updateShowPoints(active),
        updateShowImages: (active: boolean) => imageLogic?.updateShowImages(active),
        renderBoundingBoxesInstanced: () => boxLogic?.renderBoundingBoxesInstanced(props.groups),
        updateShowLabels: (visible: boolean) => boxLogic?.updateShowLabels(visible),
        updateShowBoxes: (visible: boolean) => boxLogic?.updateShowBoxes(visible)
    }
}