import { ref, type Ref, watch } from 'vue'
import * as THREE from 'three'
import KDBush from 'kdbush'
import { Props } from '@/components/mapview/ImageMap.vue'

// ----------------------------------------------------------------------
// TYPES
// ----------------------------------------------------------------------

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
    dataStore: any // The useDataStore instance
    isLoadingRef: Ref<boolean> // Reactive ref for loading state
    props: Props // The component props
}

interface ImageAnimationState {
    targetScale: number
    currentScale: number
    mesh: THREE.Mesh
}

// ----------------------------------------------------------------------
// RAW THREE.JS / CONSTANT VARIABLES
// ----------------------------------------------------------------------

let scene: THREE.Scene | null = null
let camera: THREE.OrthographicCamera | null = null
let renderer: THREE.WebGLRenderer | null = null
let instancedMesh: THREE.Points | null = null
let imageGroup: THREE.Group | null = null

let animationFrameId: number

// Data Caches (Raw JS Maps)
const idMap = new Map<string, number>()
const textureCache = {
    small: new Map<number, THREE.Texture>(),
    raw: new Map<number, THREE.Texture>()
}
const pendingTextures = {
    small: new Set<number>(),
    raw: new Set<number>()
}

const sharedPlaneGeo = new THREE.PlaneGeometry(1, 1)
const textureLoader = new THREE.TextureLoader()

// Mouse Interactivity
let raycaster: THREE.Raycaster = new THREE.Raycaster();
let mouse: THREE.Vector2 = new THREE.Vector2();
let ignore_hover_once = false
const hoveredPointId = ref<number | null>(null) // Track which point is hovered
const originalZ = 0.01; // Base Z position for all images
const popZ = 0.1;      // Elevated Z position for the hovered image
const maxHoverScale = 2

// KDtree
let tree: KDBush | null = null // KDTree for optimal point query
let treeToPointMap: Map<number, PointData> = new Map()

// Rendering State
let triggerRender = true
let resizeObserver: ResizeObserver | null = null
let dataStore: any

// Animation
const animationStateMap = new Map<number, ImageAnimationState>() // Key: pointId
const ANIMATION_SPEED = 0.15; // Controls the smoothness/speed of interpolation

// ----------------------------------------------------------------------
// CORE COMPOSABLE
// ----------------------------------------------------------------------

export function useMapLogic({ dataStore: store, isLoadingRef, props }: PointCloudVizParams) {
    dataStore = store

    // --- Utility Functions ---

    /**
     * Flags the scene for re-render in the next animation frame.
     */
    function updateView() {
        triggerRender = true
    }

    const updateAnimations = () => {
        let needsRender = false

        animationStateMap.forEach((state, pointId) => {
            const mesh = state.mesh

            // Interpolate the current scale towards the target scale
            const delta = state.targetScale - state.currentScale

            // If the difference is small, snap to the target to prevent jitter
            if (Math.abs(delta) < 0.001) {
                if (state.currentScale !== state.targetScale) {
                    state.currentScale = state.targetScale
                    needsRender = true
                }
                return
            }

            // Apply exponential smoothing (Lerp function)
            state.currentScale += delta * ANIMATION_SPEED

            // Retrieve the base size (pre-multiplied by ratio)
            const baseWidth = mesh.scale.x / (mesh.scale.y / (0.05 * getAdaptiveWorldSize(props.baseImageSize, camera!.zoom)))
            const baseHeight = 0.05 * getAdaptiveWorldSize(props.baseImageSize, camera!.zoom)

            // Re-apply the interpolated scale factor
            mesh.scale.x = baseWidth * state.currentScale
            mesh.scale.y = baseHeight * state.currentScale

            needsRender = true
        })

        if (needsRender) {
            updateView()
        }
    }


    const animate = () => {
        animationFrameId = requestAnimationFrame(animate)

        if (props.showImages && camera) {
            handleHover();
            updateAnimations(); // Call the new animation handler
        }

        if (renderer && scene && camera && triggerRender) {
            triggerRender = false
            renderer.render(scene, camera)
        }
    }

    // --- THREE.JS SETUP ---

    /**
     * Initializes the THREE.js scene, camera, renderer, and event listeners.
     */
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

        // 3. Renderer
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
        renderer.setSize(width, height)
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
        renderer.setClearColor(new THREE.Color(props.backgroundColor))

        // Attach to DOM
        domElement.appendChild(renderer.domElement)

        // 4. Interaction
        setupInteraction(renderer.domElement, camera)

        // 5. Image Group
        imageGroup = new THREE.Group()
        imageGroup.visible = props.showImages
        scene.add(imageGroup)

        // 6. Start animation loop
        animate()

        // 7. Resize Observer
        resizeObserver = new ResizeObserver(() => handleResize(domElement))
        resizeObserver.observe(domElement)
    }

    /**
     * Cleans up THREE.js resources and event listeners.
     */
    const cleanup = () => {
        if (animationFrameId) cancelAnimationFrame(animationFrameId)
        if (resizeObserver) resizeObserver.disconnect()

        if (renderer && renderer.domElement.parentNode) {
            renderer.domElement.parentNode.removeChild(renderer.domElement)
            renderer.dispose()
        }

        if (instancedMesh) {
            instancedMesh.geometry.dispose();
            (instancedMesh.material as THREE.PointsMaterial).dispose()
        }

        // Dispose textures to free GPU memory
        Object.values(textureCache).forEach(t => t.forEach(tc => tc.dispose()))
        Object.values(textureCache).forEach(t => t.clear())
        idMap.clear()
        treeToPointMap.clear()

        // Nullify to help GC
        scene = null
        camera = null
        renderer = null
        instancedMesh = null
        imageGroup = null
        tree = null
    }

    // --- POINT CLOUD LOGIC ---

    /**
     * Creates or updates the point cloud visualization mesh.
     */
    function processPoints(points: PointData[]) {
        if (!points || !scene || !props.pointSize) return

        // Remove old point cloud
        if (instancedMesh) {
            scene.remove(instancedMesh)
            instancedMesh.geometry.dispose();
            (instancedMesh.material as THREE.PointsMaterial).dispose()
            instancedMesh = null
        }

        isLoadingRef.value = true

        const count = points.length

        // Build buffer attributes
        const positions = new Float32Array(count * 3)
        const colors = new Float32Array(count * 3)
        idMap.clear() // Clear existing mapping

        for (let i = 0; i < count; i++) {
            const p = points[i]

            // XYZ
            positions[i * 3 + 0] = p.x
            positions[i * 3 + 1] = p.y
            positions[i * 3 + 2] = 0

            // Convert color string → rgb
            const c = new THREE.Color(p.color || 0xffffff)
            colors[i * 3 + 0] = c.r
            colors[i * 3 + 1] = c.g
            colors[i * 3 + 2] = c.b

            // Store mapping for color updates
            idMap.set(p.sha1, i)
        }

        const geometry = new THREE.BufferGeometry()
        geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3))
        geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3))

        const sprite = drawCircleSprite()

        const material = new THREE.PointsMaterial({
            size: props.pointSize * window.devicePixelRatio,
            sizeAttenuation: false,
            vertexColors: true,
            map: sprite,
            alphaTest: 0.5,
            transparent: true,
            visible: props.showPoints
        })

        instancedMesh = new THREE.Points(geometry, material)
        scene.add(instancedMesh)

        createKDTree(points)
        updateVisibleImages() // Trigger image update for new points
        updateView()
        isLoadingRef.value = false
    }

    /**
     * Toggles the visibility of the image group.
     */
    const updateShowImages = (active: boolean) => {
        if (imageGroup) {
            imageGroup.visible = active
            if (active) updateVisibleImages()
        }
    }

    /**
     * Toggles the visibility of the point cloud.
     */
    const updateShowPoints = (active: boolean) => {
        if (instancedMesh) {
            instancedMesh.visible = active
        }
    }


    // --- INTERACTION / FRUSTUM CULLING ---

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

        if (props.showImages) updateVisibleImages()
        updateView()
    }

    const handleHover = () => {
        if (!camera || !imageGroup || !props.showImages) return
        if (ignore_hover_once) {
            ignore_hover_once = false
            return
        }

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
            updateVisibleImages() // Rebuild images to apply hover effect
            updateView()
        }
    }


    const setupInteraction = (dom: HTMLCanvasElement, cam: THREE.OrthographicCamera) => {
        // --- ZOOM with Pan-to-Mouse ---
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
            updateView()

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

        renderer!.domElement.addEventListener('mousemove', onMouseMove, false)

        function onMouseMove(event: MouseEvent) {
            const rect = renderer!.domElement.getBoundingClientRect()
            mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
            mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
        }
    }

    // --- KD-Tree / Culling / Image Loading ---

    function createKDTree(points: PointData[]) {
        treeToPointMap.clear()
        tree = new KDBush(points.length)
        for (let point of points) {
            const id = tree.add(point.x, point.y)
            treeToPointMap.set(id, point)
            point.id = id
        }
        tree.finish()
    }

    function getPointsInRect(minX: number, minY: number, maxX: number, maxY: number): PointData[] {
        if (!tree) return []
        const ids = tree.range(minX, minY, maxX, maxY)
        return ids.map(id => treeToPointMap.get(id)!)
    }

    const getAdaptiveWorldSize = (baseSize: number, zoom: number): number => {
        const k = 0.5
        let targetVisualSize = baseSize * Math.pow(zoom, k)

        const minPixelSize = props.minImageSize
        const maxPixelSize = props.maxImageSize
        targetVisualSize = Math.max(minPixelSize, Math.min(targetVisualSize, maxPixelSize))

        return targetVisualSize / zoom
    }

    const getTexture = (quality: 'small' | 'raw', point: PointData): THREE.Texture | null => {
        // 1. Check if loaded
        if (textureCache[quality].has(point.id!)) {
            return textureCache[quality].get(point.id!)!
        }

        // 2. Check if already loading
        if (pendingTextures[quality].has(point.id!)) {
            if (quality === 'raw' && textureCache['small'].has(point.id!)) {
                return textureCache['small'].get(point.id!)!
            }
            return null
        }

        // 3. Start Load
        pendingTextures[quality].add(point.id!)
        const url = dataStore.baseImgUrl + quality + '/' + point.sha1

        textureLoader.load(
            url,
            (tex) => {
                tex.colorSpace = THREE.SRGBColorSpace
                textureCache[quality].set(point.id!, tex)
                pendingTextures[quality].delete(point.id!)

                // Rebuild the scene to add the mesh with the new texture
                updateVisibleImages()
            },
            undefined,
            (err) => {
                console.error('Texture loading failed:', err)
                pendingTextures[quality].delete(point.id!)
                updateVisibleImages()
            }
        )

        // 4. Fallback while loading
        if (quality === 'raw' && textureCache['small'].has(point.id!)) {
            return textureCache['small'].get(point.id!)!
        }
        return null
    }

    const debounceImageUpdate = () => {
        // No actual debounce timer used in the original code, 
        // calling directly to mimic original behavior.
        updateVisibleImages()
    }



    const updateVisibleImages = () => {
        if (!props.showImages || !camera || !imageGroup || !props.points.length) return

        // Dispose existing materials/geometries before clearing
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
        let imgQuality: 'small' | 'raw' = 'small'
        if (zoom > 5) imgQuality = 'raw'

        const gridSize = getGridStepSize(zoom) * 1.5
        let visiblePoints = getPointsInRect(left - gridSize, bottom - gridSize, right + gridSize, top + gridSize)

        if (gridSize > 2) {
            visiblePoints = selectImagesForGrid(visiblePoints, gridSize).map(p => treeToPointMap.get(p.id))
        }

        // 4. Calculate Shared Size
        const worldSize = getAdaptiveWorldSize(props.baseImageSize, zoom)

        // Clear state map for points no longer visible, but retain scale for points still visible
        const nextAnimationStateMap = new Map<number, ImageAnimationState>()


const sharedMaterial = new THREE.ShaderMaterial({
    uniforms: {
        map: { value: null },
        borderColor: { value: new THREE.Color(0x000000) },
        borderWidth: { value: 0.02 },
        borderRadius: { value: 0.1 },
        showBorder: { value: 1.0 },
        applyRadius: { value: 1.0 },
        textureSize: { value: new THREE.Vector2(1, 1) }
    },
    vertexShader: `
        varying vec2 vUv;
        
        void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
    `,
    fragmentShader: `
        uniform sampler2D map;
        uniform vec3 borderColor;
        uniform float borderWidth;
        uniform float borderRadius;
        uniform float showBorder;
        uniform float applyRadius;
        uniform vec2 textureSize;
        varying vec2 vUv;
        
        vec3 linearToSRGB(vec3 color) {
            return pow(color, vec3(1.0 / 2.2));
        }
        
        float roundedBoxSDF(vec2 centerPos, vec2 size, float radius) {
            return length(max(abs(centerPos) - size + radius, 0.0)) - radius;
        }
        
        void main() {
            vec4 texColor = texture2D(map, vUv);
            
            // Calculate aspect ratio
            float aspectRatio = textureSize.x / textureSize.y;
            
            // Center position (-0.5 to 0.5)
            vec2 pos = vUv - 0.5;
            
            // Adjust for aspect ratio
            if (aspectRatio > 1.0) {
                pos.x *= aspectRatio;
            } else {
                pos.y /= aspectRatio;
            }
            
            // Box size
            vec2 size = vec2(aspectRatio > 1.0 ? aspectRatio : 1.0, aspectRatio > 1.0 ? 1.0 : 1.0 / aspectRatio) * 0.5;
            
            // Use border radius only if applyRadius is enabled
            float radius = borderRadius * applyRadius;
            
            // Distance from rounded box edge
            float dist = roundedBoxSDF(pos, size, radius);
            
            // Border is the region between the outer edge and inner edge
            float outerEdge = 0.0;
            float innerEdge = -borderWidth;
            
            // Is this pixel in the border region?
            float inBorder = step(innerEdge, dist) * step(dist, outerEdge);
            
            // Apply showBorder toggle
            float borderMask = inBorder * showBorder;
            
            // Mix between texture color and border color
            vec3 finalColor = mix(texColor.rgb, borderColor, borderMask);
            
            // Apply color space conversion
            vec3 color = linearToSRGB(finalColor);
            
            // Apply rounded corners (clip outside) only if applyRadius is enabled
            float alpha = texColor.a * mix(1.0, step(dist, 0.0), applyRadius);
            
            gl_FragColor = vec4(color, alpha);
        }
    `,
    transparent: true
});
        // console.log('update visible')
        // 5. Render and Update Animation Targets
        visiblePoints.forEach((p) => {
            const isHovered = hoveredPointId.value === p.id
            const targetScaleFactor = isHovered ? maxHoverScale : 1 // Target scale is 2x for hover
            const zPosition = isHovered ? popZ : originalZ

            let quality: 'small' | 'raw' = (isHovered || imgQuality === 'raw') ? 'raw' : 'small'

            const texture = getTexture(quality, p)

            if (!texture) return

            // --- Core Scale Logic ---
            const finalWidth = 0.05 * worldSize * p.ratio // Base calculated width
            const finalHeight = 0.05 * worldSize          // Base calculated height

            // 1. Get existing animation state or create new
            let state = animationStateMap.get(p.id!)
            if (!state) {
                state = {
                    targetScale: targetScaleFactor,
                    currentScale: targetScaleFactor === maxHoverScale ? ((1 + maxHoverScale) / 2) : 1, // Start a little offset to ensure it scales if new
                    mesh: null! // Will be set below
                }
            }
            state.targetScale = targetScaleFactor // Update target

            // 2. Create Mesh
            // const material = new THREE.MeshBasicMaterial({
            //     map: texture,
            //     color: 0xffffff,
            //     transparent: true
            // })

            const material = sharedMaterial.clone()
            texture.colorSpace = THREE.SRGBColorSpace
            material.uniforms.map.value = texture;
            if (texture.image) {
                material.uniforms.textureSize.value.set(
                    (texture.image as any).width,
                    (texture.image as any).height
                );
            }
            if (p.border) {
                material.uniforms.showBorder.value = true
                // material.uniforms.borderWidth.value = 0.04
                material.uniforms.borderColor.value = new THREE.Color(p.color)
            } else {
                material.uniforms.showBorder.value = false
            }

            const plane = new THREE.Mesh(sharedPlaneGeo, material)

            // IMPORTANT: Initialize scale using the current scale from the state
            // The animation loop will update this on every frame.
            plane.scale.set(
                finalWidth * state.currentScale,
                finalHeight * state.currentScale,
                1
            )

            plane.position.set(p.x, p.y, zPosition)
            plane.userData.pointId = p.id

            if (isHovered) plane.renderOrder = 999

            imageGroup!.add(plane)

            // Update the state map with the new mesh
            state.mesh = plane
            nextAnimationStateMap.set(p.id!, state)
        })

        // Replace the old map with the new one for visible points
        animationStateMap.clear()
        nextAnimationStateMap.forEach((v, k) => animationStateMap.set(k, v))

        updateView()
    }

    // --- GRID UTILS ---

    function getGridStepSize(
        zoom: number,
        baseGridSize: number = 3.0,
        zoomThresholds: number[] = [0.25, 0.5, 1, 2, 4, 8, 16, 32]
    ): number {
        for (let i = zoomThresholds.length - 1; i >= 0; i--) {
            if (zoom >= zoomThresholds[i]) {
                return baseGridSize / Math.pow(2, i)
            }
        }
        return baseGridSize * 2
    }

    function selectImagesForGrid(
        points: PointData[],
        gridStepSize: number
    ): PointData[] {
        const gridCells = new Map<string, { point: PointData; distSq: number }>()

        for (const point of points) {
            const cellX = Math.floor(point.x / gridStepSize)
            const cellY = Math.floor(point.y / gridStepSize)
            const cellKey = `${cellX},${cellY}`

            // Corner of the grid cell
            const gridPointX = cellX * gridStepSize
            const gridPointY = (cellY + 1) * gridStepSize

            const dx = point.x - gridPointX
            const dy = point.y - gridPointY
            const distSq = dx * dx + dy * dy

            const existing = gridCells.get(cellKey)
            if (!existing || distSq < existing.distSq) {
                gridCells.set(cellKey, { point, distSq })
            }
        }
        return Array.from(gridCells.values()).map(entry => entry.point)
    }

    function drawCircleSprite(): THREE.CanvasTexture {
        const size = 128
        const canvas = document.createElement("canvas")
        canvas.width = size
        canvas.height = size

        const ctx = canvas.getContext("2d")!
        ctx.clearRect(0, 0, size, size)

        ctx.fillStyle = "white"
        ctx.beginPath()
        ctx.arc(size / 2, size / 2, size / 2, 0, Math.PI * 2)
        ctx.closePath()
        ctx.fill()

        const texture = new THREE.CanvasTexture(canvas)
        texture.minFilter = THREE.LinearFilter
        texture.magFilter = THREE.LinearFilter
        texture.generateMipmaps = false

        return texture
    }

    // Add a watch for image size props within the logic file to trigger image update
    watch(() => [props.baseImageSize, props.maxImageSize, props.minImageSize], () => {
        updateVisibleImages()
    })

    // Watch for background color changes
    watch(() => props.backgroundColor, (newColor) => {
        if (renderer) renderer.setClearColor(new THREE.Color(newColor))
        updateView()
    })


    return {
        init,
        cleanup,
        processPoints,
        updateShowImages,
        updateShowPoints,
        updateView, // Exposed for external render trigger if needed
    }
}