import * as THREE from 'three'
import { ImageAtlas } from '@/data/models'
import { InstancedImageMaterial } from './InstancedImageMaterial'
import { PointData } from './useMapLogic'

export class AtlasLayer {
    public mesh: THREE.InstancedMesh
    private geometry: THREE.PlaneGeometry
    private material: InstancedImageMaterial

    constructor(atlas: ImageAtlas, texture: THREE.Texture, points: PointData[], currentSheetIdx: number) {
        const gridCols = atlas.width / atlas.cellWidth
        const gridRows = atlas.height / atlas.cellHeight
        const cellRatio = atlas.cellWidth / atlas.cellHeight
        const count = points.length

        // --- ANTI-BLEEDING LOGIC ---
        // We inset the UVs by a fraction of a pixel to stop flickering borders
        const bleedMargin = 0.5; // half-pixel inset
        const invTexW = 1.0 / atlas.width;
        const invTexH = 1.0 / atlas.height;
        
        // Convert pixel margin to normalized UV space (0.0 to 1.0)
        // We multiply by grid size because the transform happens BEFORE the grid scaling in your shader
        const uvMarginX = (bleedMargin * invTexW) * gridCols;
        const uvMarginY = (bleedMargin * invTexH) * gridRows;

        this.geometry = new THREE.PlaneGeometry(1, 1)
        this.material = new InstancedImageMaterial({ map: texture, transparent: true }, gridCols, gridRows)
        this.mesh = new THREE.InstancedMesh(this.geometry, this.material, count)

        const offsets = new Float32Array(count * 2)
        const uvTransforms = new Float32Array(count * 4) 
        const tints = new Float32Array(count * 3)
        const borders = new Float32Array(count * 3) // Added missing attribute
        const matrix = new THREE.Matrix4()
        const colorHelper = new THREE.Color()

        points.forEach((p, i) => {
            // 1. Physical Quad Transform
            matrix.makeScale(p.ratio, 1, 1) 
            matrix.setPosition(p.x, p.y, 0)
            this.mesh.setMatrixAt(i, matrix)

            // 2. Atlas Cell Offset
            const mapping = atlas.sha1Mapping[p.sha1]
            if (mapping) {
                const cellIndex = mapping[1]
                offsets[i * 2] = (cellIndex % gridCols) / gridCols
                offsets[i * 2 + 1] = (gridRows - 1 - Math.floor(cellIndex / gridCols)) / gridRows
            }

            // 3. UV Correction Logic (Aspect Ratio + Bleed Fix)
            const imgRatio = p.ratio
            let scaleX = 1.0
            let scaleY = 1.0

            if (imgRatio > cellRatio) {
                scaleY = cellRatio / imgRatio
            } else {
                scaleX = imgRatio / cellRatio
            }

            // Apply the bleed margin to the scale and offset
            // We shrink the sampling area slightly and shift the start point inward
            uvTransforms[i * 4] = scaleX - (uvMarginX * 2.0)
            uvTransforms[i * 4 + 1] = scaleY - (uvMarginY * 2.0)
            uvTransforms[i * 4 + 2] = (1.0 - scaleX) * 0.5 + uvMarginX
            uvTransforms[i * 4 + 3] = (1.0 - scaleY) * 0.5 + uvMarginY

            // 4. Color & Border Attributes
            colorHelper.set('#FFFFFF')
            tints[i * 3] = colorHelper.r
            tints[i * 3 + 1] = colorHelper.g
            tints[i * 3 + 2] = colorHelper.b

            // Initialize borders to avoid undefined behavior in shader
            borders[i * 3] = 0;
            borders[i * 3 + 1] = 0;
            borders[i * 3 + 2] = 0;
        })

        this.geometry.setAttribute('vOffset', new THREE.InstancedBufferAttribute(offsets, 2))
        this.geometry.setAttribute('vUvTransform', new THREE.InstancedBufferAttribute(uvTransforms, 4))
        this.geometry.setAttribute('vTint', new THREE.InstancedBufferAttribute(tints, 3))
        this.geometry.setAttribute('vBorderCol', new THREE.InstancedBufferAttribute(borders, 3))
        
        this.mesh.instanceMatrix.needsUpdate = true
    }

    public dispose() {
        this.geometry.dispose()
        this.material.dispose()
    }
}