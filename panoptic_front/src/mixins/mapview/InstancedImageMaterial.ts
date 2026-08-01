import { ZoomParams } from '@/data/models';
import * as THREE from 'three';

export class InstancedImageMaterial extends THREE.MeshBasicMaterial {
    private _zoomRef: { value: number } = { value: 1.0 };
    private _zoomParams = new THREE.Vector3(1.0, 0.1, 0.11);
    private _radius = { value: 0.05 };
    private _showAsPoint = { value: 0.0 };

    constructor(parameters: THREE.MeshBasicMaterialParameters, collNb: number, rowNb: number) {
        super(parameters);

        this.onBeforeCompile = (shader) => {
            shader.uniforms.uGridCols = { value: collNb };
            shader.uniforms.uGridRows = { value: rowNb };
            shader.uniforms.uRadius = this._radius;
            shader.uniforms.uZoom = this._zoomRef;
            shader.uniforms.uZoomParams = { value: this._zoomParams };
            shader.uniforms.uShowAsPoint = this._showAsPoint;

            shader.vertexShader = `
                attribute vec2 vOffset;
                attribute vec4 vUvTransform; 
                attribute vec4 vTint;
                attribute vec3 vBorderCol;
                attribute float vBorderWidth;
                attribute float vRatioAttr;
                attribute float vDesaturate;

                varying vec2 vMappedUv;
                varying vec2 vRawUv;
                varying vec4 vInstanceTint;
                varying vec3 vInstanceBorder;
                varying float vInstanceBorderWidth;
                varying float vRatio;
                varying float vInstanceDesaturate;

                uniform float uGridCols;
                uniform float uGridRows;
                uniform float uZoom;
                uniform vec3 uZoomParams;
                uniform float uShowAsPoint;

                ${shader.vertexShader}
            `.replace(
                `#include <begin_vertex>`,
                `
                vec3 transformed = vec3( position );
                float h  = uZoomParams.x;
                float z1 = uZoomParams.y;
                float z2 = uZoomParams.z;

                // Use the attribute directly
                vRatio = vRatioAttr; 

                // When showing as point, use uniform 1:1 scale
                if(uShowAsPoint > 0.5) {
                    // Point size is always h/uZoom for consistent sizing
                    float pointScale = h/10.0 / uZoom;
                    transformed.xy *= pointScale;
                } else {
                    // Normal image rendering with zoom scaling
                    float zoomScale = h;
                    if(uZoom >= z1 && uZoom < z2) {
                        zoomScale = h * (z1 / uZoom);
                    } else if(uZoom >= z2) {
                        zoomScale = h * (z1 / z2);
                    }

                    // FIT LOGIC: Calculate scale to fit in 1.0 x 1.0 box
                    vec2 sizeScale;
                    if(vRatio > 1.0) {
                        // Landscape: Width is 1.0, Height is 1/Ratio
                        sizeScale = vec2(1.0, 1.0 / vRatio);
                    } else {
                        // Portrait: Height is 1.0, Width is Ratio
                        sizeScale = vec2(vRatio, 1.0);
                    }

                    transformed.xy *= sizeScale * zoomScale;
                }
                `
            ).replace(
                `#include <uv_vertex>`,
                `
                #include <uv_vertex>
                vRawUv = uv;
                
                float margin = 0.0005; 
                vec2 safeUv = mix(vec2(margin), vec2(1.0 - margin), uv);
                vec2 correctedUv = safeUv * vUvTransform.xy + vUvTransform.zw;
                vMappedUv = (correctedUv / vec2(uGridCols, uGridRows)) + vOffset;
                
                vInstanceTint = vTint;
                vInstanceBorder = vBorderCol;
                vInstanceBorderWidth = vBorderWidth;
                vInstanceDesaturate = vDesaturate;
                `
            );

            shader.fragmentShader = `
                varying vec2 vMappedUv;
                varying vec2 vRawUv;
                varying vec4 vInstanceTint;
                varying vec3 vInstanceBorder;
                varying float vInstanceBorderWidth;
                varying float vRatio;
                varying float vInstanceDesaturate;

                uniform float uRadius;
                uniform float uShowAsPoint;
                uniform float uZoom;
                uniform vec3 uZoomParams;

                float sdRoundedBox(vec2 p, vec2 b, float r) {
                    vec2 q = abs(p) - b + r;
                    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - r;
                }

                ${shader.fragmentShader}
            `.replace(
                `#include <map_fragment>`,
                `
                // If showing as point, render a colored circle
                if(uShowAsPoint > 0.5) {
    vec2 p = vRawUv - 0.5;
    float dist = length(p);

    // Use a larger radius (0.5 fills the square) to ensure visibility
    float pointRadius = 0.45;
    // Antialias over roughly one screen pixel (fwidth) rather than a fixed slice of the quad:
    // a constant uv-space width is a large fraction of the dot's radius, so the fade read as a
    // pale halo where the dot blended into the white background.
    float aa = fwidth(dist);
    float pointMask = smoothstep(pointRadius + aa, pointRadius - aa, dist);

    // Instead of multiplying, use the logic from your image mode:
    // This ensures that if it's visible in image mode, it's visible here.
    vec3 finalRGB = mix(vInstanceBorder, vInstanceTint.rgb, vInstanceTint.a);
    
    // Use 1.0 instead of texelColor.a since there is no texture
    diffuseColor = vec4(finalRGB, pointMask); 
} else {
                    // Normal image rendering
                    vec2 dimensions;
                    if(vRatio > 1.0) {
                        dimensions = vec2(1.0, 1.0 / vRatio);
                    } else {
                        dimensions = vec2(vRatio, 1.0);
                    }
                    
                    vec2 p = (vRawUv - 0.5) * dimensions;
                    vec2 b = dimensions * 0.5;
                    
                    float d = sdRoundedBox(p, b, uRadius);
                    
                    float aa = 0.002; 
                    float outsideMask = smoothstep(aa, 0.0, d);
                    // The border shrinks as the camera zooms in (scale = z1/uZoom, capped at 1):
                    // zoomed out, the coloured ring is the only way to read a group's colour, but
                    // on a close-up a full-width ring would just cover the photo. Zooming below z1
                    // keeps it at full strength, so it is thickest exactly when thumbnails are
                    // smallest. A floor proportional to the set border width (MIN_BORDER_RATIO)
                    // stops it from vanishing entirely at extreme zoom-in.
                    const float MIN_BORDER_RATIO = 0.15;
                    float borderScale = clamp(uZoomParams.y / max(uZoom, uZoomParams.y), 0.0, 1.0);
                    float borderW = vInstanceBorderWidth * max(borderScale, MIN_BORDER_RATIO);
                    float borderMask = smoothstep(aa, 0.0, d + borderW);

                    vec4 texelColor = texture2D( map, vMappedUv );

                    // Grey out (per-pixel luminance, not a flat colour wash) before tinting, so a
                    // dimmed-group photo and a blue selection overlay compose instead of fighting.
                    float luminance = dot(texelColor.rgb, vec3(0.299, 0.587, 0.114));
                    vec3 desaturatedColor = mix(texelColor.rgb, vec3(luminance), vInstanceDesaturate);

                    // Mix between original texture and tint color based on tint alpha
                    vec3 tintedColor = mix(desaturatedColor, vInstanceTint.rgb, vInstanceTint.a);
                    vec3 tintedBorderColor = mix(vInstanceBorder.rgb, vInstanceTint.rgb, vInstanceTint.a);

                    vec3 finalRGB = mix(tintedBorderColor, tintedColor, borderMask);
                    // The border ring is drawn inside the image box, so it must be opaque even
                    // where the sampled texel is semi-transparent — at the bottom edge the plane's
                    // uv lands on the atlas cell's opaque/transparent boundary, and with a thin
                    // (zoom-scaled) border the whole ring would otherwise go see-through, letting
                    // the white background bleed through as a white glow on the bottom border.
                    diffuseColor = vec4(finalRGB, max(texelColor.a, 1.0 - borderMask) * outsideMask);
                }
                `
            );
            this.userData.shader = shader;
        };
    }

    public setRadius(radius: number) {
        this._radius.value = radius;
        if (this.userData.shader) {
            this.userData.shader.uniforms.uRadius.value = radius;
        }
    }

    public setZoomParams(params: ZoomParams) {
        this._zoomParams.set(params.h, params.z1, params.z2);
        if (this.userData.shader) {
            this.userData.shader.uniforms.uZoomParams.value = this._zoomParams;
        }
    }

    public setZoomReference(zoomUniform: { value: number }) {
        this._zoomRef = zoomUniform;
        if (this.userData.shader) {
            this.userData.shader.uniforms.uZoom = zoomUniform;
        }
    }

    public setShowAsPoint(show: boolean) {
        this._showAsPoint.value = show ? 1.0 : 0.0;
        // Point mode drops the depth buffer entirely: dots are flat single-colour discs with
        // nothing to occlude, so depth ordering buys nothing, while depth-writing antialiased
        // edges blocked the disc behind them and traced a pale ring around every overlap.
        // Without depth write the alphaTest cut can go back to ~0, keeping the edges smooth.
        // Image mode keeps depth (photos really do occlude each other and the z tiers order them).
        this.depthWrite = !show;
        const alphaTest = show ? 0.0 : 0.5;
        if (this.alphaTest !== alphaTest) {
            // Crossing 0 toggles the USE_ALPHATEST define, so the program must be rebuilt.
            this.alphaTest = alphaTest;
            this.needsUpdate = true;
        }
        if (this.userData.shader) {
            this.userData.shader.uniforms.uShowAsPoint.value = this._showAsPoint.value;
        }
    }
}