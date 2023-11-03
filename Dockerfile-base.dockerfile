FROM python:3

RUN pip3 install torch torchvision torchaudio 
RUN pip3 install --force-reinstall transformers typing-extensions

RUN python3 -c 'from transformers import CLIPModel, CLIPProcessor, CLIPTokenizer;CLIPModel.from_pretrained("openai/clip-vit-base-patch32");CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32");CLIPTokenizer.from_pretrained("openai/clip-vit-base-patch32");'
