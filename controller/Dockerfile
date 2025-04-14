FROM python:latest
WORKDIR /app
COPY . .

RUN pip install --upgrade pip \
 && pip install -r requirements.txt

#CMD ["python", "controller.py"]
CMD ["flask", "run", "--host", "0.0.0.0"]
