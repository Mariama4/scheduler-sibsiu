FROM python:3.11

RUN apt-get update && apt-get install -y poppler-utils

ENV Path /usr/local/bin:$Path

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY ./ /app

EXPOSE 8888

CMD ["python", "main.py"]
