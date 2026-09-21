import sys

MODEL = "openai/clip-vit-base-patch32"


def main() -> int:
    # 1. torch est-il importable et fonctionnel ?
    print("Vérification de torch...")
    import torch

    print(f"  torch {torch.__version__} importé.")
    print(f"  CUDA disponible : {torch.cuda.is_available()}")

    # 2. panopticml est-il importable ?
    print("Vérification de panopticml...")
    import panopticml
    from panopticml.compute.transformer import CLIPTransformer

    # 3. Vectorisation d'une image de test via CLIPTransformer.to_vector.
    from PIL import Image

    print(f"Chargement du modèle CLIP ({MODEL})...")
    transformer = CLIPTransformer(MODEL)

    print("Vectorisation d'une image de test...")
    image = Image.new("RGB", (224, 224), color=(127, 127, 127))
    vector = transformer.to_vector(image)

    print(f"  Vecteur obtenu : dimension {vector.shape}, dtype {vector.dtype}")

    if vector.ndim != 1 or vector.size == 0:
        print("ERREUR : le vecteur produit est invalide.", file=sys.stderr)
        return 1

    print("Installation vérifiée : torch et panopticml fonctionnent correctement.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
