FROM ceressorbonne/panoptic-clip-base:latest

COPY . /app 
WORKDIR ./app/panoptic_back/ 

RUN pip3 install -U pip
RUN pip3 install --force-reinstall typing-extensions
RUN pip3 install .

RUN mkdir -p /data/
RUN chown -R 1000:1000 /data/
RUN chmod -R 777 /data/

ENV PANOPTIC_HOST="0.0.0.0"
ENV IS_DOCKER="True"

EXPOSE 8000

CMD ["panoptic"]
