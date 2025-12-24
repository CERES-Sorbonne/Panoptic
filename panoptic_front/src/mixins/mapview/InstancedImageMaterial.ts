import * as THREE from 'three';

export class InstancedImageMaterial extends THREE.MeshBasicMaterial {
    constructor(parameters: THREE.MeshBasicMaterialParameters, collNb: number, rowNb: number) {
        super(parameters);

        this.onBeforeCompile = (shader) => {
            // 1. Define Uniforms
            shader.uniforms.uGridCols = { value: collNb };
            shader.uniforms.uGridRows = { value: rowNb };
            shader.uniforms.uBorderWidth = { value: 0.00 };

            // 2. VERTEX SHADER
            shader.vertexShader = `
                attribute vec2 vOffset;
                attribute vec4 vUvTransform; 
                attribute vec3 vTint;
                attribute vec3 vBorderCol;
                
                varying vec2 vMappedUv;
                varying vec2 vRawUv; 
                varying vec3 vInstanceTint;
                varying vec3 vInstanceBorder;

                uniform float uGridCols;
                uniform float uGridRows;

                ${shader.vertexShader}
            `.replace(
                `#include <uv_vertex>`,
                `
                #include <uv_vertex>
                
                vRawUv = uv;
                
                // --- BLEED PREVENTION ---
                // Apply a tiny inset to the UV sampling to prevent neighbors from leaking in
                float margin = 0.0005; 
                vec2 safeUv = mix(vec2(margin), vec2(1.0 - margin), uv);
                
                // Apply internal cell scaling/centering (Corrects Aspect Ratio)
                vec2 correctedUv = safeUv * vUvTransform.xy + vUvTransform.zw;
                
                // Scale down to fit one cell and add the grid offset
                vMappedUv = (correctedUv / vec2(uGridCols, uGridRows)) + vOffset;
                
                vInstanceTint = vTint;
                vInstanceBorder = vBorderCol;
                `
            );

            // 3. FRAGMENT SHADER
            shader.fragmentShader = `
                varying vec2 vMappedUv;
                varying vec2 vRawUv;
                varying vec3 vInstanceTint;
                varying vec3 vInstanceBorder;

                uniform float uBorderWidth;

                ${shader.fragmentShader}
            `.replace(
                `#include <map_fragment>`,
                `
                vec4 texelColor = texture2D( map, vMappedUv );
                texelColor.rgb *= vInstanceTint;

                // --- STABLE PROCEDURAL BORDER ---
                float b = uBorderWidth;
                vec3 finalRGB = texelColor.rgb;

                // Only calculate border if width is significantly greater than 0
                if (b > 0.0005) {
                    // We inset the border test coordinates so they don't flicker at 0.0/1.0
                    float inset = 0.001;
                    vec2 stableUv = vRawUv * (1.0 - inset * 2.0) + inset;
                    
                    // Smoothstep provides anti-aliasing and prevents 1px "jumps"
                    float aa = 0.002; 
                    float borderMask = smoothstep(b, b + aa, stableUv.x) * smoothstep(b, b + aa, stableUv.y) * smoothstep(b, b + aa, 1.0 - stableUv.x) * smoothstep(b, b + aa, 1.0 - stableUv.y);
                    
                    finalRGB = mix(vInstanceBorder, texelColor.rgb, borderMask);
                }

                // Use the texture alpha so the border respects the sprite's shape
                diffuseColor = vec4(finalRGB, texelColor.a);
                `
            );

            (this as any).userData.shader = shader;
        };
    }

    public setBorderWidth(width: number) {
        const shader = (this as any).userData.shader;
        if (shader) {
            shader.uniforms.uBorderWidth.value = width;
        }
    }
}