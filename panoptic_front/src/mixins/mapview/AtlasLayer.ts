import * as THREE from 'three'
import { ImageAtlas, PointData, ZoomParams } from '@/data/models'
import { InstancedImageMaterial } from './InstancedImageMaterial'

export class AtlasLayer {
    public mesh: THREE.InstancedMesh
    private geometry: THREE.PlaneGeometry
    public material: InstancedImageMaterial 
    
    // Store references to points and atlas for subsequent updates
    private points: PointData[]
    private atlas: ImageAtlas
    private matrixHelper = new THREE.Matrix4()
    private colorHelper = new THREE.Color()

    constructor(atlas: ImageAtlas, texture: THREE.Texture, points: PointData[], currentSheetIdx: number) {
        this.points = points
        this.atlas = atlas
        
        const gridCols = atlas.width / atlas.cellWidth
        const gridRows = atlas.height / atlas.cellHeight
        const count = points.length

        this.geometry = new THREE.PlaneGeometry(1, 1)
        this.material = new InstancedImageMaterial({ map: texture, transparent: true }, gridCols, gridRows)
        this.mesh = new THREE.InstancedMesh(this.geometry, this.material, count)

        // Initialize attributes with empty arrays
        this.geometry.setAttribute('vOffset', new THREE.InstancedBufferAttribute(new Float32Array(count * 2), 2))
        this.geometry.setAttribute('vUvTransform', new THREE.InstancedBufferAttribute(new Float32Array(count * 4), 4))
        this.geometry.setAttribute('vTint', new THREE.InstancedBufferAttribute(new Float32Array(count * 3), 3))
        this.geometry.setAttribute('vBorderCol', new THREE.InstancedBufferAttribute(new Float32Array(count * 3), 3))

        // Initial population of all attributes
        this.updateUVsAndOffsets()
        this.updatePositions()
        this.updateTints()
        this.updateBorderColors()
        
        this.mesh.frustumCulled = false;
        this.mesh.matrixAutoUpdate = false;
        this.mesh.updateMatrixWorld(true);
    }

    /**
     * Updates Matrices based on point x, y and ratio.
     */
    public updatePositions() {
        this.points.forEach((p, i) => {
            this.matrixHelper.makeScale(p.ratio, 1, 1) 
            this.matrixHelper.setPosition(p.x, p.y, 0)
            this.mesh.setMatrixAt(i, this.matrixHelper)
        })
        this.mesh.instanceMatrix.needsUpdate = true
    }

    /**
     * Updates the vTint attribute. Assumes points have a color property or defaults to white.
     */
    public updateTints() {
        const attr = this.geometry.getAttribute('vTint') as THREE.InstancedBufferAttribute
        const array = attr.array as Float32Array

        this.points.forEach((p, i) => {
            // If PointData has a specific color, use it, otherwise white
            this.colorHelper.set(p.tint || '#FFFFFF')
            array[i * 3] = this.colorHelper.r
            array[i * 3 + 1] = this.colorHelper.g
            array[i * 3 + 2] = this.colorHelper.b
        })
        attr.needsUpdate = true
    }

    /**
     * Updates the vBorderCol attribute.
     */
    public updateBorderColors() {
        const attr = this.geometry.getAttribute('vBorderCol') as THREE.InstancedBufferAttribute
        const array = attr.array as Float32Array

        this.points.forEach((p, i) => {
            this.colorHelper.set(p.borderColor || '#000000')
            array[i * 3] = this.colorHelper.r
            array[i * 3 + 1] = this.colorHelper.g
            array[i * 3 + 2] = this.colorHelper.b
        })
        attr.needsUpdate = true
    }

    /**
     * Internal helper to handle UV math and Atlas mapping
     */
    private updateUVsAndOffsets() {
        const gridCols = this.atlas.width / this.atlas.cellWidth
        const gridRows = this.atlas.height / this.atlas.cellHeight
        const cellRatio = this.atlas.cellWidth / this.atlas.cellHeight
        
        const bleedMargin = 0.5; 
        const uvMarginX = (bleedMargin / this.atlas.width) * gridCols;
        const uvMarginY = (bleedMargin / this.atlas.height) * gridRows;

        const offAttr = this.geometry.getAttribute('vOffset') as THREE.InstancedBufferAttribute
        const uvAttr = this.geometry.getAttribute('vUvTransform') as THREE.InstancedBufferAttribute
        
        const offArray = offAttr.array as Float32Array
        const uvArray = uvAttr.array as Float32Array

        this.points.forEach((p, i) => {
            const mapping = this.atlas.sha1Mapping[p.sha1]
            if (mapping) {
                const cellIndex = mapping[1]
                offArray[i * 2] = (cellIndex % gridCols) / gridCols
                offArray[i * 2 + 1] = (gridRows - 1 - Math.floor(cellIndex / gridCols)) / gridRows
            }

            const imgRatio = p.ratio
            let scaleX = 1.0, scaleY = 1.0
            if (imgRatio > cellRatio) scaleY = cellRatio / imgRatio
            else scaleX = imgRatio / cellRatio

            uvArray[i * 4] = scaleX - (uvMarginX * 2.0)
            uvArray[i * 4 + 1] = scaleY - (uvMarginY * 2.0)
            uvArray[i * 4 + 2] = (1.0 - scaleX) * 0.5 + uvMarginX
            uvArray[i * 4 + 3] = (1.0 - scaleY) * 0.5 + uvMarginY
        })

        offAttr.needsUpdate = true
        uvAttr.needsUpdate = true
    }

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