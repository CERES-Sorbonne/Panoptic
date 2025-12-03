// usePointLogic.ts
import * as THREE from 'three'
import { Ref } from 'vue'
import { PointData } from './useMapLogic'
import { Props } from '@/components/mapview/ImageMap.vue'

// --- SHADER DEFINITIONS (UPDATED with opacityScale) ---
const vertexShader = `
    uniform float pointSize;
    attribute vec3 color;
    varying vec3 vColor;
    varying float vPointSize;

    void main() {
        gl_PointSize = pointSize; 
        vPointSize = pointSize;
        vColor = color; 
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
`

const fragmentShader = `
    uniform float opacityScale; // NEW: Uniform for overall mesh opacity control
    varying vec3 vColor;
    varying float vPointSize;

        vec3 linearToSRGB(vec3 color) {
            return pow(color, vec3(1.0 / 2.2));
        }
    
    void main() {
        vec2 pointCenter = gl_PointCoord - vec2(0.5);
        float distanceToCenter = length(pointCenter);
        float radius = 0.5;
        float smoothness = 2.0 / vPointSize;
        float alpha = smoothstep(radius, radius - smoothness, distanceToCenter);

        vec3 color = linearToSRGB(vColor);
        // Apply opacityScale to the final alpha
        gl_FragColor = vec4(color, alpha * opacityScale);
        
        // Update discard check to respect the overall dimming
        if (alpha * opacityScale < 0.01) discard;
    }
`

interface PointLogicParams {
    scene: THREE.Scene
    props: Props
    isLoadingRef: Ref<boolean>
    idMap: Map<string, number>
    updateView: () => void
}

export function usePointLogic({ scene, props, isLoadingRef, idMap, updateView }: PointLogicParams) {
    let allPointsGroup: THREE.Group | null = null
    let selectedPointsMesh: THREE.Points | null = null
    let unselectedPointsMesh: THREE.Points | null = null

    // Constants for the two planes
    const SELECTED_OPACITY = 1.0
    const UNSELECTED_OPACITY = 0.2
    const UNSELECTED_COLOR = new THREE.Color('#e9e9e9') // Dark gray for dimmed points
    const DEFAULT_POINT_COLOR = new THREE.Color(0x1E90FF) // Sky Blue fallback

    /**
     * Cleans up existing point meshes.
     */
    function cleanupPoints() {
        if (allPointsGroup) {
            scene.remove(allPointsGroup)
            allPointsGroup.traverse((child) => {
                if (child instanceof THREE.Points) {
                    child.geometry.dispose()
                    if (Array.isArray(child.material)) {
                        child.material.forEach(m => m.dispose())
                    } else {
                        (child.material as THREE.Material).dispose()
                    }
                }
            })
            allPointsGroup = null
            selectedPointsMesh = null
            unselectedPointsMesh = null
        }
    }


    /**
     * Creates or updates the point cloud visualization mesh using two separate planes.
     */
    function processPoints(points: PointData[]) {
        if (!points || !scene || !props.pointSize) return
        
        cleanupPoints()

        isLoadingRef.value = true
        idMap.clear()

        // --- 1. Partition Data ---
        const hasSelection = Object.keys(props.selectedPoints).length > 0
        const selectedData: PointData[] = []
        const unselectedData: PointData[] = []
        

        points.forEach((p, i) => {
            // Ensure sha1 is mapped to index for external lookups
            idMap.set(p.sha1, i) 

            // If nothing is selected, ALL points are "selected" (full opacity plane)
            const isSelected = !hasSelection || (hasSelection && props.selectedPoints[p.sha1])

            if (isSelected) {
                selectedData.push(p)
            } else {
                unselectedData.push(p)
            }
        })


        // --- 2. Function to Build Geometry and Materials ---
        const buildPointsMesh = (data: PointData[], opacity: number, useSubduedColor: boolean): THREE.Points | null => {
            if (data.length === 0) return null

            const positions = new Float32Array(data.length * 3)
            const colors = new Float32Array(data.length * 3)

            data.forEach((p, i) => {
                positions[i * 3 + 0] = p.x
                positions[i * 3 + 1] = p.y
                positions[i * 3 + 2] = 0

                let pointColor
                if (useSubduedColor) {
                    // Use dark gray for unselected points
                    pointColor = UNSELECTED_COLOR
                } else {
                    // Use point's color or Sky Blue default
                    pointColor = new THREE.Color(p.color || DEFAULT_POINT_COLOR)
                }
                
                colors[i * 3 + 0] = pointColor.r
                colors[i * 3 + 1] = pointColor.g
                colors[i * 3 + 2] = pointColor.b
            })

            const geometry = new THREE.BufferGeometry()
            geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3))
            geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3))

            const material = new THREE.ShaderMaterial({
                uniforms: {
                    pointSize: { value: props.pointSize * window.devicePixelRatio },
                    opacityScale: { value: opacity }, // Pass the unique opacity
                },
                vertexShader: vertexShader,
                fragmentShader: fragmentShader,
                transparent: true,
                depthTest: true,
                visible: props.showPoints
            })

            return new THREE.Points(geometry, material)
        }


        // --- 3. Create Meshes ---
        allPointsGroup = new THREE.Group()

        // Selected Mesh (or all points if nothing selected)
        selectedPointsMesh = buildPointsMesh(selectedData, SELECTED_OPACITY, false)
        if (selectedPointsMesh) {
            selectedPointsMesh.renderOrder = 10;
            allPointsGroup.add(selectedPointsMesh)
        }

        // Unselected Mesh (only rendered if there is a selection)
        unselectedPointsMesh = buildPointsMesh(unselectedData, UNSELECTED_OPACITY, true)
        if (unselectedPointsMesh) {
            unselectedPointsMesh.renderOrder = 5; // Draw behind selected points
            allPointsGroup.add(unselectedPointsMesh)
        }

        // --- 4. Add to Scene and Finish ---
        scene.add(allPointsGroup)
        updateView()
        isLoadingRef.value = false
    }

    /**
     * Toggles the visibility of the point cloud.
     */
    const updateShowPoints = (active: boolean) => {
        if (allPointsGroup) {
            allPointsGroup.visible = active
        }
        updateView()
    }

    return {
        processPoints,
        updateShowPoints,
        getInstancedMesh: () => allPointsGroup // Changed to return the parent group
    }
}