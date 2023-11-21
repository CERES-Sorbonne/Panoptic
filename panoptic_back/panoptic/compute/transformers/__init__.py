import numpy as np
from PIL import Image
from transformers import MobileNetV2Model, AutoImageProcessor, CLIPModel, CLIPProcessor, CLIPTokenizer, logging

logging.set_verbosity_error()


class GoogleTransformer:
    def __init__(self):
        self.model = MobileNetV2Model.from_pretrained("google/mobilenet_v2_1.0_224")
        self.processor = AutoImageProcessor.from_pretrained("google/mobilenet_v2_1.0_224")

    @property
    def can_handle_text(self):
        return False

    def to_vector(self, image: Image) -> np.ndarray:
        input1 = self.processor(images=image, return_tensors="pt")
        output1 = self.model(**input1)
        pooled_output1 = output1[1].detach().numpy()
        vector = pooled_output1.flatten()
        return vector


class CLIPTransformer:
    def __init__(self):
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        self.tokenizer = CLIPTokenizer.from_pretrained("openai/clip-vit-base-patch32")

    @property
    def can_handle_text(self):
        return True

    def to_vector(self, image: Image) -> np.ndarray:
        image = self.processor(
            text=None,
            images=image,
            return_tensors="pt"
        )["pixel_values"]
        embedding = self.model.get_image_features(image)
        # convert the embeddings to numpy array
        embedding_as_np = embedding.cpu().detach().numpy()
        return embedding_as_np[0]

    def to_text_vector(self, text: str) -> np.ndarray:
        inputs = self.tokenizer(text, return_tensors="pt")
        text_embeddings = self.model.get_text_features(**inputs)
        # convert the embeddings to numpy array
        embedding_as_np = text_embeddings.cpu().detach().numpy()
        return embedding_as_np.reshape(1, -1)


def get_transformer(model="small"):
    if model == "small":
        return GoogleTransformer()
    elif model == "clip":
        return CLIPTransformer()
    else:
        return GoogleTransformer()