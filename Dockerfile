FROM tyrannas/panoptic-clip-base:latest

COPY . /app 
WORKDIR ./app/panoptic_back/ 

RUN pip3 install --force-reinstall typing-extensions
RUN python3 setup.py install

ENV PANOPTIC_DATA=/data/
ENV IS_DOCKER=True

EXPOSE 8000

CMD ["panoptic", "--host", "--server", "--folder", "/data/images"]
