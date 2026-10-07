import { ZoomParams } from '@/data/models';
import * as THREE from 'three';

export class HDImageMaterial extends THREE.MeshBasicMaterial {
    private _zoomRef: { value: number } = { value: 1.0 };
    private _zoomParams = new THREE.Vector3(1.0, 0.1, 0.8);
    private _ratio = { value: 1.0 };
    private _borderColor = { value: new THREE.Color(0x000000) };
    private _borderWidth = { value: 0.00 };
    private _radius = { value: 0.05 };
    private _tint = { value: new THREE.Color(0xFFFFFF) };
    private _tintAlpha = { value: 0.0 };
    // Texture lookup: uv * xy + zw. Crops or flips the image without a new texture.
    private _uvTransform = { value: new THREE.Vector4(1, 1, 0, 0) };
    private _desaturate = { value: 0.0 };
    // 1: the tint covers the border too, as on the grid thumbnails.
    private _tintBorder = { value: 0.0 };
    // Fades towards the white scene background like the atlas thumbnails' vOpacity.
    private _fade = { value: 1.0 };

    constructor(parameters: THREE.MeshBasicMaterialParameters) {
        super(parameters);

        this.onBeforeCompile = (shader) => {
            shader.uniforms.uZoom = this._zoomRef;
            shader.uniforms.uZoomParams = { value: this._zoomParams };
            shader.uniforms.uRatio = this._ratio;
            shader.uniforms.uBorderColor = this._borderColor;
            shader.uniforms.uBorderWidth = this._borderWidth;
            shader.uniforms.uRadius = this._radius;
            shader.uniforms.uTint = this._tint;
            shader.uniforms.uTintAlpha = this._tintAlpha;
            shader.uniforms.uUvTransform = this._uvTransform;
            shader.uniforms.uDesaturate = this._desaturate;
            shader.uniforms.uTintBorder = this._tintBorder;
            shader.uniforms.uFade = this._fade;

            shader.vertexShader = `
                varying vec2 vRawUv;
                uniform float uZoom;
                uniform vec3 uZoomParams;
                uniform float uRatio;
                ${shader.vertexShader}
            `.replace(
                `#include <begin_vertex>`,
                `
                vec3 transformed = vec3( position );
                float h  = uZoomParams.x;
                float z1 = uZoomParams.y;
                float z2 = uZoomParams.z;

                float zoomScale = h;
                if(uZoom >= z1 && uZoom < z2) {
                    zoomScale = h * (z1 / uZoom);
                } else if(uZoom >= z2) {
                    zoomScale = h * (z1 / z2);
                }

                // Calculate vector scale to fit in 1.0 x 1.0 box while keeping aspect ratio
                vec2 sizeScale;
                if(uRatio > 1.0) {
                    // Landscape: Width fixed to 1.0, Height reduces
                    sizeScale = vec2(1.0, 1.0 / uRatio);
                } else {
                    // Portrait/Square: Height fixed to 1.0, Width reduces
                    sizeScale = vec2(uRatio, 1.0);
                }

                // Apply specific X and Y scaling
                transformed.xy *= sizeScale * zoomScale;
                `
            ).replace(
                `#include <uv_vertex>`,
                `#include <uv_vertex>
                 vRawUv = uv;`
            );

            shader.fragmentShader = `
                varying vec2 vRawUv;
                uniform float uBorderWidth;
                uniform float uRatio;
                uniform float uZoom;
                uniform vec3 uZoomParams;
                uniform vec3 uBorderColor;
                uniform float uRadius;
                uniform vec3 uTint;
                uniform float uTintAlpha;
                uniform vec4 uUvTransform;
                uniform float uDesaturate;
                uniform float uTintBorder;
                uniform float uFade;

                float sdRoundedBox(vec2 p, vec2 b, float r) {
                    vec2 q = abs(p) - b + r;
                    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - r;
                }

                ${shader.fragmentShader}
            `.replace(
                `#include <map_fragment>`,
                `
                vec2 dimensions;
                if(uRatio > 1.0) {
                    dimensions = vec2(1.0, 1.0 / uRatio);
                } else {
                    dimensions = vec2(uRatio, 1.0);
                }
                
                vec2 p = (vRawUv - 0.5) * dimensions;
                vec2 b = dimensions * 0.5;
                
                float d = sdRoundedBox(p, b, uRadius);
                
                float edgeSoftness = 0.002;
                float outsideMask = smoothstep(edgeSoftness, 0.0, d);
                // Same zoom-scaled border as the instanced grid thumbnails (see
                // InstancedImageMaterial): the ring thins out as you zoom in so it never covers a
                // close-up, with a floor so it stays visible at extreme zoom-in.
                const float MIN_BORDER_RATIO = 0.15;
                float borderScale = clamp(uZoomParams.y / max(uZoom, uZoomParams.y), 0.0, 1.0);
                float borderW = uBorderWidth * max(borderScale, MIN_BORDER_RATIO);
                float borderMask = smoothstep(edgeSoftness, 0.0, d + borderW);

                vec4 texelColor = texture2D( map, vRawUv * uUvTransform.xy + uUvTransform.zw );

                float luminance = dot(texelColor.rgb, vec3(0.299, 0.587, 0.114));
                vec3 desaturatedColor = mix(texelColor.rgb, vec3(luminance), uDesaturate);
                vec3 fadedColor = mix(vec3(1.0), desaturatedColor, uFade);
                vec3 fadedBorder = mix(vec3(1.0), uBorderColor, uFade);
                vec3 tintedColor = mix(fadedColor, uTint, uTintAlpha);
                vec3 borderColor = mix(fadedBorder, uTint, uTintAlpha * uTintBorder);
                vec3 finalRGB = mix(borderColor, tintedColor, borderMask);

                // opacity is MeshBasicMaterial's own uniform (declared upstream in the
                // unmodified part of this shader) — folded in here since this replace fully
                // overwrites diffuseColor.a, which would otherwise drop the hover fade animation.
                diffuseColor = vec4(finalRGB, max(texelColor.a, 1.0 - borderMask) * outsideMask * opacity);
                `
            );

            this.userData.shader = shader;
        };
    }

    public setZoomReference(zoomUniform: { value: number }) {
        this._zoomRef = zoomUniform;
    }

    public setZoomParams(params: ZoomParams) {
        this._zoomParams.set(params.h, params.z1, params.z2);
    }

    public setRatio(ratio: number) {
        this._ratio.value = ratio;
    }

    public setRadius(radius: number) {
        this._radius.value = radius;
    }

    public setBorder(width: number, color: string) {
        this._borderWidth.value = width
        this._borderColor.value = new THREE.Color(color)
    }

    public setTint(tint: string | undefined, alpha: number | undefined) {
        this._tint.value.set(tint || '#FFFFFF')
        this._tintAlpha.value = alpha ?? 0.0
    }

    public setUvTransform(scaleX: number, scaleY: number, offsetX: number, offsetY: number) {
        this._uvTransform.value.set(scaleX, scaleY, offsetX, offsetY)
    }

    public setDesaturate(amount: number | undefined) {
        this._desaturate.value = amount ?? 0.0
    }

    public setTintBorder(tintBorder: boolean) {
        this._tintBorder.value = tintBorder ? 1.0 : 0.0
    }

    public setFade(amount: number | undefined) {
        this._fade.value = amount ?? 1.0
    }
}