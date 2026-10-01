FROM python:3.10-alpine

WORKDIR /app


RUN apk add --no-cache gcc g++ musl-dev linux-headers python3-dev


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY . .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
