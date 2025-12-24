import * as THREE from 'three';

export class InstancedImageMaterial extends THREE.MeshBasicMaterial {
    constructor(parameters: THREE.MeshBasicMaterialParameters, collNb, rowNb) {
        super(parameters);

        // Define internal variables for the shader logic
        this.onBeforeCompile = (shader) => {
            // 1. VERTEX SHADER: Pass data from CPU to GPU
            shader.vertexShader = `
    attribute vec2 vOffset;
    attribute vec3 vTint;
    attribute vec3 vBorderCol;
    
    varying vec2 vUvOffset;
    varying vec3 vInstanceTint;
    varying vec3 vInstanceBorder;
    varying vec2 vUv; // <-- ADD THIS

    ${shader.vertexShader}
`.replace(
                `#include <uv_vertex>`,
                `
    #include <uv_vertex>
    vUvOffset = vOffset;
    vInstanceTint = vTint;
    vInstanceBorder = vBorderCol;
    vUv = uv; // <-- MAP THE ATTRIBUTE TO OUR VARYING
    `
            );

            shader.fragmentShader = `
    varying vec2 vUvOffset;
    varying vec3 vInstanceTint;
    varying vec3 vInstanceBorder;
    varying vec2 vUv; // <-- ADD THIS

    uniform float uBorderWidth;
    uniform float uGridCols;
    uniform float uGridRows;

    ${shader.fragmentShader}
`.replace(
                `#include <map_fragment>`,
                `
    // A. Map the Spritesheet
    vec2 scaledUv = vUv * vec2(1.0/uGridCols, 1.0/uGridRows) + vUvOffset;
    
    // Note: use 'map' which is the uniform name for your texture
    vec4 texelColor = texture2D( map, scaledUv );
    
    // B. Apply Tint
    texelColor.rgb *= vInstanceTint;

    // C. Procedural Border Logic
    // We use vUv (0.0 to 1.0) to detect the edges of the quad
    float b = uBorderWidth;
    float borderMask = step(b, vUv.x) * step(b, vUv.y) * step(b, 1.0 - vUv.x) * step(b, 1.0 - vUv.y);
    
    vec3 finalRGB = mix(vInstanceBorder, texelColor.rgb, borderMask);

    diffuseColor = vec4(finalRGB, texelColor.a);
    `
            );

            // Add uniforms to the material so we can control them from JS
            shader.uniforms.uBorderWidth = { value: 0.00 }; // Default border size
            // Inside InstancedImageMaterial's onBeforeCompile:
            shader.uniforms.uGridCols = { value: collNb };
            shader.uniforms.uGridRows = { value: rowNb };

            // Store reference to update later
            (this as any).userData.shader = shader;
        };
    }

    // Helper to toggle borders globally
    public setBorderWidth(width: number) {
        const shader = (this as any).userData.shader;
        if (shader) shader.uniforms.uBorderWidth.value = width;
    }
}