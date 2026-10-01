FROM python:3.10-alpine

# Define a pasta de trabalho dentro do contentor
WORKDIR /app

# Copia e instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto do código
COPY . .

# Expõe a porta que a aplicação vai utilizar
EXPOSE 8000

# Comando para iniciar o servidor (ajusta conforme uses FastAPI/Uvicorn ou Flask)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]