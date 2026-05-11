FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir .

ENV BOKHALD_HOST=0.0.0.0
ENV BOKHALD_DATA_DIR=/data

EXPOSE 8080

CMD ["bokhald"]
