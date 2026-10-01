FROM python:3.10-alpine

WORKDIR /app

# Instala as dependências de sistema necessárias para compilar bibliotecas no Alpine
RUN apk add --no-cache gcc g++ musl-dev linux-headers python3-dev

# Copia e instala as dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto do código e a pasta do ChromaDB
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
