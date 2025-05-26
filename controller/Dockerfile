FROM python:latest
WORKDIR /app
COPY . .

RUN pip install --upgrade pip \
 && pip install -r requirements.txt

CMD ["python", "controller.py"]
