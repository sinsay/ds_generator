FROM rpc_base:v1

COPY ./ /src/

# RUN apk add --update --no-cache \
        # linux-headers \
        # build-base

RUN pip install --upgrade -r /src/requirements.txt

WORKDIR /src

EXPOSE 50051

CMD ["python", "rpc_server.py"]
