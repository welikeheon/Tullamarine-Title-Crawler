FROM python:3.8.2
LABEL NAME="Tullamarine URL Parser" Version=3.0.0
EXPOSE 3000

WORKDIR /app/src
ADD . /app

# Using pip:
RUN python3 -m pip install -r requirements.txt && \
    mkdir -p ./downloads
CMD ["python3", "main.py"]