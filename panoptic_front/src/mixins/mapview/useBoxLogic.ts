// useBoxLogic.ts
import * as THREE from 'three'
import { CSS2DObject, CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import { BoundingBox } from './useMapLogic'
import { Props } from '@/components/mapview/ImageMap.vue'
import { objValues } from '@/data/builder'
import { MapGroup } from '@/data/models'


interface BoxLogicParams {
    scene: THREE.Scene
    camera: THREE.OrthographicCamera
    props: Props
    labelRenderer: CSS2DRenderer | null
    updateView: () => void
}

// Store the calculated pixel width of each unique label text to prevent recalculation
const labelWidthCache = new Map<string, number>()

// --- Module-level Material and Group References ---
// We use module-level materials for consistent opacity control.
let selectedMaterial: THREE.MeshBasicMaterial | null = null;
let unselectedMaterial: THREE.MeshBasicMaterial | null = null;

// The geometry is now split into two planes for opacity control
let selectedBoxGroup: THREE.Group | null = null;
let unselectedBoxGroup: THREE.Group | null = null;
let allBoxGroups: THREE.Group | null = null; // Parent group for visibility toggle

// Store current data for re-rendering on zoom
let currentGroups: MapGroup[] = []
let currentBoundingBoxThickness: number = 3

const Z_POS = 0.10
const PIXEL_TO_WORLD_FACTOR = 0.01 // Factor to convert pixel thickness to world units
const SELECTED_LABEL_OPACITY = 1.0
const UNSELECTED_LABEL_OPACITY = 0.1
// ------------------------------------------------------------------------

// Utility function for creating and styling the 2D label DIV element
function createAndMeasureLabelDiv(group: MapGroup, boxColor: THREE.Color): HTMLDivElement {
    const textContent = group.name || 'Box'

    const labelDiv = document.createElement('div')
    labelDiv.className = 'box-label'
    labelDiv.textContent = textContent

    // Apply CSS styles
    labelDiv.style.color = 'white'
    labelDiv.style.fontWeight = 'bold'
    labelDiv.style.fontSize = '12px'
    labelDiv.style.backgroundColor = boxColor.getStyle();
    labelDiv.style.padding = '2px 6px'
    labelDiv.style.borderRadius = '2px'
    labelDiv.style.whiteSpace = 'nowrap'

    return labelDiv
}

export function useBoxLogic({ scene, camera, props, labelRenderer, updateView }: BoxLogicParams) {
    // Local state for labels
    const labelObjects: CSS2DObject[] = []

    /**
     * Clears all box meshes and their associated HTML labels.
     */
    const cleanupBoxes = () => {
        if (allBoxGroups) {
            scene.remove(allBoxGroups)

            // Dispose of geometries on all children
            allBoxGroups.traverse((child) => {
                if (child instanceof THREE.InstancedMesh) {
                    child.geometry.dispose()
                }
            })

            selectedBoxGroup = null
            unselectedBoxGroup = null
            allBoxGroups = null
        }

        // Remove all 2D labels
        while (labelObjects.length) {
            const label = labelObjects.pop()
            if (label) {
                scene.remove(label)
                label.element.remove()
            }
        }
    }

    /**
     * Initializes and returns the necessary materials for the two planes.
     */
    function getMaterials() {
        if (!selectedMaterial) {
            // Material for selected/all boxes: fully opaque
            selectedMaterial = new THREE.MeshBasicMaterial({
                transparent: true,
                opacity: 1.0,
                depthTest: true
            });
        }
        if (!unselectedMaterial) {
            // Material for unselected boxes: low opacity
            unselectedMaterial = new THREE.MeshBasicMaterial({
                transparent: true,
                opacity: 0.05,
                depthTest: true
            });
        }
        return { selectedMaterial, unselectedMaterial };
    }


    /**
     * Utility function to handle the repetitive matrix and color assignments.
     */
    function applyBoxInstanceData(
        box: BoundingBox, i: number,
        worldThickness: number, halfThickness: number, Z_POS: number,
        boxColor: THREE.Color, matrix: THREE.Matrix4,
        hMesh: THREE.InstancedMesh, vMesh: THREE.InstancedMesh,
        labelObject: CSS2DObject | null, isSelected: boolean, labelOpacity
    ) {
        const { minX, minY, maxX, maxY } = box
        const width = maxX - minX
        const height = maxY - minY
        const fullVerticalLength = height + worldThickness

        // --- 3D BORDER LOGIC ---

        // Bottom edge (horizontal)
        matrix.makeScale(width + worldThickness - 2 * halfThickness, 1, 1)
        matrix.setPosition(minX + width / 2, minY - halfThickness, Z_POS)
        hMesh.setMatrixAt(i * 2, matrix)
        hMesh.setColorAt(i * 2, boxColor)

        // Top edge (horizontal)
        matrix.makeScale(width + worldThickness - 2 * halfThickness, 1, 1)
        matrix.setPosition(minX + width / 2, maxY + halfThickness, Z_POS)
        hMesh.setMatrixAt(i * 2 + 1, matrix)
        hMesh.setColorAt(i * 2 + 1, boxColor)

        // Left edge (vertical)
        matrix.makeScale(1, fullVerticalLength + 2 * halfThickness, 1)
        matrix.setPosition(minX - halfThickness, minY + height / 2, Z_POS)
        vMesh.setMatrixAt(i * 2, matrix)
        vMesh.setColorAt(i * 2, boxColor)

        // Right edge (vertical)
        matrix.makeScale(1, fullVerticalLength + 2 * halfThickness, 1)
        matrix.setPosition(maxX + halfThickness, minY + height / 2, Z_POS)
        vMesh.setMatrixAt(i * 2 + 1, matrix)
        vMesh.setColorAt(i * 2 + 1, boxColor)

        // Label Positioning (only for fully visible boxes)
        if (labelObject) {
            const labelX = minX - halfThickness + (maxX - minX) / 2
            const labelY = maxY + halfThickness

            const pixelOffset = 2
            const worldOffset = (pixelOffset / camera.zoom) * PIXEL_TO_WORLD_FACTOR

            labelObject.position.set(labelX + worldOffset, labelY, Z_POS)
            labelObject.element.style.opacity = labelOpacity.toString()
        }
    }


    function renderBoundingBoxesInstanced(groups: MapGroup[], pixelThickness: number = 3) {
        if (!scene || !camera || !labelRenderer) return

        // 1. Clean up existing
        cleanupBoxes()

        if (groups.length === 0) return
        if (!props.showBoxes) return

        // --- Data & State Prep ---
        currentGroups = groups // Store for zoom updates
        currentBoundingBoxThickness = pixelThickness

        const hasSelected = objValues(props.selectedGroups).length > 0

        const selectedGroupData: MapGroup[] = []
        const unselectedGroupData: MapGroup[] = []

        // Partition data into two arrays based on selection status
        groups.forEach(group => {
            const isSelected = hasSelected && props.selectedGroups[group.id];

            if (!hasSelected || isSelected) {
                // If nothing is selected, ALL groups go to the selected plane (opacity 1.0)
                selectedGroupData.push(group)
            } else {
                // If something IS selected, unselected groups go to the unselected plane (opacity 0.05 border)
                unselectedGroupData.push(group)
            }
        })

        const numSelected = selectedGroupData.length
        const numUnselected = unselectedGroupData.length

        // Calculate thickness in world units based on current zoom
        const worldThickness = (pixelThickness / camera.zoom) * PIXEL_TO_WORLD_FACTOR
        const halfThickness = worldThickness / 2

        // --- Setup Meshes and Geometries ---
        const { selectedMaterial, unselectedMaterial } = getMaterials();

        allBoxGroups = new THREE.Group() // Parent group for visibility toggle
        allBoxGroups.renderOrder = 100

        selectedBoxGroup = new THREE.Group()
        unselectedBoxGroup = new THREE.Group()

        const horizontalGeo = new THREE.PlaneGeometry(1, worldThickness)
        const verticalGeo = new THREE.PlaneGeometry(worldThickness, 1)

        const matrix = new THREE.Matrix4()
        const defaultColor = new THREE.Color('#AAAAAA') // Default border color


        // --- 1. SELECTED / ALL BOXES (Border Opacity 1.0, Label Opacity 1.0) ---
        if (numSelected > 0) {
            const hMesh = new THREE.InstancedMesh(horizontalGeo, selectedMaterial, numSelected * 2)
            const vMesh = new THREE.InstancedMesh(verticalGeo, selectedMaterial, numSelected * 2)

            // Explicitly create instance color attributes
            hMesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(numSelected * 2 * 3), 3);
            vMesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(numSelected * 2 * 3), 3);

            selectedGroupData.forEach((group, i) => {
                const box = group.box
                const boxColor = box.color ? new THREE.Color(box.color) : defaultColor

                // Create label for the box
                const labelDiv = createAndMeasureLabelDiv(group, boxColor)
                labelDiv.style.zIndex = "2";
                const labelObject = new CSS2DObject(labelDiv)
                // Label visibility depends on both 'showBoxes' and 'showLabels' props
                labelObject.visible = props.showBoxes

                // Set 3D and 2D Positions, applying full label opacity
                applyBoxInstanceData(
                    box, i, worldThickness, halfThickness, Z_POS, boxColor, matrix,
                    hMesh, vMesh, labelObject, true, SELECTED_LABEL_OPACITY
                )

                labelObjects.push(labelObject)
                scene.add(labelObject)
            })

            hMesh.instanceMatrix.needsUpdate = true
            vMesh.instanceMatrix.needsUpdate = true
            hMesh.instanceColor.needsUpdate = true
            vMesh.instanceColor.needsUpdate = true

            selectedBoxGroup.add(hMesh, vMesh)
        }


        // --- 2. UNSELECTED BOXES (Border Opacity 0.05, Label Opacity 0.3) ---
        if (numUnselected > 0) {

            const hMesh = new THREE.InstancedMesh(horizontalGeo, unselectedMaterial, numUnselected * 2)
            const vMesh = new THREE.InstancedMesh(verticalGeo, unselectedMaterial, numUnselected * 2)

            // Explicitly create instance color attributes
            hMesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(numUnselected * 2 * 3), 3);
            vMesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(numUnselected * 2 * 3), 3);

            const lowOpacityBorderColor = new THREE.Color('#333333'); // Subdued color for unselected borders

            unselectedGroupData.forEach((group, i) => {
                const box = group.box

                // Create label for the unselected box
                // const boxColorForLabel = box.color ? new THREE.Color(box.color) : defaultColor
                // const labelDiv = createAndMeasureLabelDiv(group, boxColorForLabel)
                // const labelObject = new CSS2DObject(labelDiv)
                // labelObject.visible = props.showBoxes

                // Draw boxes and create label object. Pass UNSELECTED_LABEL_OPACITY
                applyBoxInstanceData(
                    box, i, worldThickness, halfThickness, Z_POS - 0.1, lowOpacityBorderColor, matrix,
                    hMesh, vMesh, null, false, UNSELECTED_LABEL_OPACITY
                )

                // labelObjects.push(labelObject)
                // scene.add(labelObject)
            })

            hMesh.instanceMatrix.needsUpdate = true
            vMesh.instanceMatrix.needsUpdate = true
            hMesh.instanceColor.needsUpdate = true
            vMesh.instanceColor.needsUpdate = true

            unselectedBoxGroup.add(hMesh, vMesh)
        }

        // --- Final Assembly ---
        allBoxGroups.add(selectedBoxGroup, unselectedBoxGroup)
        scene.add(allBoxGroups)
        updateView()
    }




    /**
     * Updates the world thickness of instanced boxes on zoom.
     */
    function updateBoundingBoxesOnZoom() {
        if (currentGroups.length > 0) {
            // Re-render using the stored groups and thickness with updated zoom level
            renderBoundingBoxesInstanced(
                currentGroups,
                currentBoundingBoxThickness
            )
        }
    }

    /**
     * Toggles the visibility of all box meshes and their labels.
     */
    function updateShowBoxes(visible: boolean) {
        // Toggle the parent group visibility
        if (allBoxGroups) {
            allBoxGroups.visible = visible
        }

        // Labels visibility must be synced with the main box toggle
        labelObjects.forEach(label => {
            // Labels are only visible if 'updateShowLabels' is true AND 'updateShowBoxes' is true
            label.visible = visible && props.showBoxes
        })

        updateView()
    }

    /**
     * Toggles visibility of only the 2D labels.
     */
    function updateShowLabels(visible: boolean) {
        // Only show labels if the main boxes toggle is also active
        const boxesAreVisible = allBoxGroups && allBoxGroups.visible

        labelObjects.forEach(label => {
            label.visible = visible && boxesAreVisible
        })

        updateView()
    }

    return {
        renderBoundingBoxesInstanced,
        updateBoundingBoxesOnZoom,
        cleanupBoxes,
        updateShowLabels,
        getBoundingBoxes: () => allBoxGroups,
        updateShowBoxes
    }
}