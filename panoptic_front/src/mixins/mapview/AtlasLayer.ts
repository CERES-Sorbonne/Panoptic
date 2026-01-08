import * as THREE from 'three'
import { ImageAtlas, ZoomParams } from '@/data/models'
import { InstancedImageMaterial } from './InstancedImageMaterial'
import { PointData } from './useMapLogic'

export class AtlasLayer {
    public mesh: THREE.InstancedMesh
    private geometry: THREE.PlaneGeometry
    public material: InstancedImageMaterial // Public so Renderer can access easily

    constructor(atlas: ImageAtlas, texture: THREE.Texture, points: PointData[], currentSheetIdx: number) {
        const gridCols = atlas.width / atlas.cellWidth
        const gridRows = atlas.height / atlas.cellHeight
        const cellRatio = atlas.cellWidth / atlas.cellHeight
        const count = points.length

        // --- ANTI-BLEEDING LOGIC ---
        const bleedMargin = 0.5; 
        const invTexW = 1.0 / atlas.width;
        const invTexH = 1.0 / atlas.height;
        
        const uvMarginX = (bleedMargin * invTexW) * gridCols;
        const uvMarginY = (bleedMargin * invTexH) * gridRows;

        this.geometry = new THREE.PlaneGeometry(1, 1)
        
        // Use transparent: true if your images have cutouts, 
        // but remember to set texture.generateMipmaps = true in MapRenderer for panning performance
        this.material = new InstancedImageMaterial({ map: texture, transparent: false }, gridCols, gridRows)
        this.mesh = new THREE.InstancedMesh(this.geometry, this.material, count)

        const offsets = new Float32Array(count * 2)
        const uvTransforms = new Float32Array(count * 4) 
        const tints = new Float32Array(count * 3)
        const borders = new Float32Array(count * 3) 
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

            uvTransforms[i * 4] = scaleX - (uvMarginX * 2.0)
            uvTransforms[i * 4 + 1] = scaleY - (uvMarginY * 2.0)
            uvTransforms[i * 4 + 2] = (1.0 - scaleX) * 0.5 + uvMarginX
            uvTransforms[i * 4 + 3] = (1.0 - scaleY) * 0.5 + uvMarginY

            // 4. Color & Border Attributes
            colorHelper.set('#FFFFFF')
            tints[i * 3] = colorHelper.r
            tints[i * 3 + 1] = colorHelper.g
            tints[i * 3 + 2] = colorHelper.b

            borders[i * 3] = 0;
            borders[i * 3 + 1] = 0;
            borders[i * 3 + 2] = 0;
        })

        this.geometry.setAttribute('vOffset', new THREE.InstancedBufferAttribute(offsets, 2))
        this.geometry.setAttribute('vUvTransform', new THREE.InstancedBufferAttribute(uvTransforms, 4))
        this.geometry.setAttribute('vTint', new THREE.InstancedBufferAttribute(tints, 3))
        this.geometry.setAttribute('vBorderCol', new THREE.InstancedBufferAttribute(borders, 3))
        
        // --- PERFORMANCE OPTIMIZATIONS ---
        this.mesh.frustumCulled = false;      // Stops CPU checking bounds for every point
        this.mesh.matrixAutoUpdate = false;   // The points themselves don't move
        this.mesh.updateMatrixWorld(true);
        this.mesh.instanceMatrix.needsUpdate = true
    }

    /**
     * Links the material's zoom uniform to the shared global uniform object
     */
    public setZoomReference(zoomUniform: { value: number }) {
        this.material.setZoomReference(zoomUniform);
    }

    public setZoomParams(params: ZoomParams) {
        this.material.setZoomParams(params)
    }

    public dispose() {
        this.geometry.dispose()
        this.material.dispose()
        this.mesh.dispose()
    }
}