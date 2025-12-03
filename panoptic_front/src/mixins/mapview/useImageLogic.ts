// useImageLogic.ts
import * as THREE from 'three'
import { Ref } from 'vue'
import { PointData } from './useMapLogic'
import { Props } from '@/components/mapview/ImageMap.vue'
import KDBush from 'kdbush'
import { objValues } from '@/data/builder'

// --- CONSTANTS ---
const sharedPlaneGeo = new THREE.PlaneGeometry(1, 1)
const textureLoader = new THREE.TextureLoader()
const originalZ = 0.01 // Base Z position for all images
const popZ = 0.1      // Elevated Z position for the hovered image
const maxHoverScale = 2
const ANIMATION_SPEED = 0.15 // Controls the smoothness/speed of interpolation

interface TextureCache {
    small: Map<number, THREE.Texture>
    raw: Map<number, THREE.Texture>
}

interface ImageAnimationState {
    targetScale: number
    currentScale: number
    mesh: THREE.Mesh
}

interface ImageLogicParams {
    scene: THREE.Scene
    camera: THREE.OrthographicCamera
    props: Props
    dataStore: any
    tree: {t: KDBush | null}
    treeToPointMap: Map<number, PointData>
    hoveredPointId: Ref<number | null>
    updateView: () => void
}

export function useImageLogic({ scene, camera, props, dataStore, tree, treeToPointMap, hoveredPointId, updateView }: ImageLogicParams) {
    let imageGroup: THREE.Group | null = null
    
    // Data Caches
    const textureCache: TextureCache = {
        small: new Map<number, THREE.Texture>(),
        raw: new Map<number, THREE.Texture>()
    }
    const pendingTextures = {
        small: new Set<number>(),
        raw: new Set<number>()
    }
    const animationStateMap = new Map<number, ImageAnimationState>() // Key: pointId

    // --- UTILS ---

    const getAdaptiveWorldSize = (baseSize: number, zoom: number): number => {
        const k = 0.5
        let targetVisualSize = baseSize * Math.pow(zoom, k)

        const minPixelSize = props.minImageSize
        const maxPixelSize = props.maxImageSize
        targetVisualSize = Math.max(minPixelSize, Math.min(targetVisualSize, maxPixelSize))

        return targetVisualSize / zoom
    }

    function getPointsInRect(minX: number, minY: number, maxX: number, maxY: number): PointData[] {
        if (!tree.t) return []
        const ids = tree.t.range(minX, minY, maxX, maxY)
        return ids.map(id => treeToPointMap.get(id)!)
    }

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

    const getTexture = (quality: 'small' | 'raw', point: PointData): THREE.Texture | null => {
        if (textureCache[quality].has(point.id!)) {
            return textureCache[quality].get(point.id!)!
        }
        if (pendingTextures[quality].has(point.id!)) {
            if (quality === 'raw' && textureCache['small'].has(point.id!)) {
                return textureCache['small'].get(point.id!)!
            }
            return null
        }

        pendingTextures[quality].add(point.id!)
        const url = dataStore.baseImgUrl + quality + '/' + point.sha1

        textureLoader.load(
            url,
            (tex) => {
                tex.colorSpace = THREE.SRGBColorSpace
                textureCache[quality].set(point.id!, tex)
                pendingTextures[quality].delete(point.id!)
                updateVisibleImages()
            },
            undefined,
            (err) => {
                console.error('Texture loading failed:', err)
                pendingTextures[quality].delete(point.id!)
                updateVisibleImages()
            }
        )

        if (quality === 'raw' && textureCache['small'].has(point.id!)) {
            return textureCache['small'].get(point.id!)!
        }
        return null
    }

    // --- ANIMATION ---
    const updateAnimations = () => {
        let needsRender = false

        animationStateMap.forEach((state, pointId) => {
            const mesh = state.mesh

            const delta = state.targetScale - state.currentScale

            if (Math.abs(delta) < 0.001) {
                if (state.currentScale !== state.targetScale) {
                    state.currentScale = state.targetScale
                    needsRender = true
                }
                return
            }

            state.currentScale += delta * ANIMATION_SPEED

            // Recalculate base dimensions based on current world size and ratio
            const zoom = camera.zoom
            const worldSize = getAdaptiveWorldSize(props.baseImageSize, zoom)
            const p = treeToPointMap.get(pointId)!
            
            const baseWidth = 0.05 * worldSize * p.ratio
            const baseHeight = 0.05 * worldSize

            mesh.scale.x = baseWidth * state.currentScale
            mesh.scale.y = baseHeight * state.currentScale

            needsRender = true
        })

        if (needsRender) {
            updateView()
        }
    }


    // --- RENDERING ---

    /**
     * Initializes the image group.
     */
    const initImageGroup = () => {
        imageGroup = new THREE.Group()
        imageGroup.visible = props.showImages
        scene.add(imageGroup)
    }


    const updateVisibleImages = () => {
        if (!props.showImages || !camera || !imageGroup || !treeToPointMap.size) return

        // Dispose existing materials/geometries before clearing
        imageGroup.children.forEach((object) => {
            if (object instanceof THREE.Mesh) {
                if (Array.isArray(object.material)) {
                    object.material.forEach(m => m.dispose())
                } else {
                    (object.material as THREE.Material).dispose()
                }
            }
        })
        imageGroup.clear()

        // 2. Calculate View Bounds
        const zoom = camera.zoom
        const left = (camera.left / zoom) + camera.position.x
        const right = (camera.right / zoom) + camera.position.x
        const top = (camera.top / zoom) + camera.position.y
        const bottom = (camera.bottom / zoom) + camera.position.y

        // 3. Culling Logic
        let imgQuality: 'small' | 'raw' = 'small'
        if (zoom > 5) imgQuality = 'raw'

        const gridSize = getGridStepSize(zoom) * 1.5
        let visiblePoints = getPointsInRect(left - gridSize, bottom - gridSize, right + gridSize, top + gridSize)

        if (gridSize > 2) {
            visiblePoints = selectImagesForGrid(visiblePoints, gridSize)
        }

        const selected = Object.keys(props.selectedPoints)
        if(selected.length) {
            const valid = new Set(selected)
            visiblePoints = visiblePoints.filter(p => valid.has(p.sha1))
        }

        // 4. Calculate Shared Size
        const worldSize = getAdaptiveWorldSize(props.baseImageSize, zoom)

        const nextAnimationStateMap = new Map<number, ImageAnimationState>()

        // Shared Shader Material for Image Planes (Fragment shader is for aspect/border/radius)
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
            // ... (Vertex and Fragment Shaders for image planes - same as original)
            vertexShader: `
        varying vec2 vUv;
        void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
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
            
            float aspectRatio = textureSize.x / textureSize.y;
            vec2 pos = vUv - 0.5;
            
            if (aspectRatio > 1.0) {
                pos.x *= aspectRatio;
            } else {
                pos.y /= aspectRatio;
            }
            
            vec2 size = vec2(aspectRatio > 1.0 ? aspectRatio : 1.0, aspectRatio > 1.0 ? 1.0 : 1.0 / aspectRatio) * 0.5;
            float radius = borderRadius * applyRadius;
            float dist = roundedBoxSDF(pos, size, radius);
            float outerEdge = 0.0;
            float innerEdge = -borderWidth;
            
            float inBorder = step(innerEdge, dist) * step(dist, outerEdge);
            float borderMask = inBorder * showBorder;
            
            vec3 finalColor = mix(texColor.rgb, borderColor, borderMask);
            vec3 color = linearToSRGB(finalColor);
            
            float alpha = texColor.a * mix(1.0, step(dist, 0.0), applyRadius);
            
            gl_FragColor = vec4(color, alpha);
        }`
            ,
            transparent: true
        });

        // 5. Render and Update Animation Targets
        visiblePoints.forEach((p) => {
            const isHovered = hoveredPointId.value === p.id
            const targetScaleFactor = isHovered ? maxHoverScale : 1
            const zPosition = isHovered ? popZ : originalZ

            let quality: 'small' | 'raw' = (isHovered || imgQuality === 'raw') ? 'raw' : 'small'

            const texture = getTexture(quality, p)

            if (!texture) return

            const finalWidth = 0.05 * worldSize * p.ratio
            const finalHeight = 0.05 * worldSize

            let state = animationStateMap.get(p.id!)
            if (!state) {
                state = {
                    targetScale: targetScaleFactor,
                    currentScale: targetScaleFactor === maxHoverScale ? ((1 + maxHoverScale) / 2) : 1,
                    mesh: null!
                }
            }
            state.targetScale = targetScaleFactor

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
                material.uniforms.borderColor.value = new THREE.Color(p.color)
            } else {
                material.uniforms.showBorder.value = false
            }

            const plane = new THREE.Mesh(sharedPlaneGeo, material)

            plane.scale.set(
                finalWidth * state.currentScale,
                finalHeight * state.currentScale,
                1
            )

            plane.position.set(p.x, p.y, zPosition)
            plane.userData.pointId = p.id

            if (isHovered) plane.renderOrder = 999

            imageGroup!.add(plane)

            state.mesh = plane
            nextAnimationStateMap.set(p.id!, state)
        })

        animationStateMap.clear()
        nextAnimationStateMap.forEach((v, k) => animationStateMap.set(k, v))
        console.log("update images")

        updateView()
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


    return {
        initImageGroup,
        updateShowImages,
        updateVisibleImages,
        updateAnimations,
        getImageGroup: () => imageGroup,
        disposeTextures: () => {
            Object.values(textureCache).forEach(t => t.forEach(tc => tc.dispose()))
            Object.values(textureCache).forEach(t => t.clear())
        }
    }
}