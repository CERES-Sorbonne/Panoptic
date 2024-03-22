FROM python:3.12.2-bullseye

RUN pip3 install -U pip
RUN pip3 install MarkupSafe
RUN pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip3 install --force-reinstall transformers typing-extensions

RUN python3 -c 'from transformers import CLIPModel, CLIPProcessor, CLIPTokenizer;CLIPModel.from_pretrained("openai/clip-vit-base-patch32");CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32");CLIPTokenizer.from_pretrained("openai/clip-vit-base-patch32");'
