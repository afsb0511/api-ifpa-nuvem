import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from json_repair import repair_json

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver

# 1. Configuração da Base Vetorial (ChromaDB)
PERSIST_DIR = "./chroma_ifpa_db"
NOME_COLECAO = "normativas_ifpa"

embeddings_consulta = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-001",
    task_type="RETRIEVAL_QUERY",
)

vectorstore_consulta = Chroma(
    persist_directory=PERSIST_DIR,
    embedding_function=embeddings_consulta,
    collection_name=NOME_COLECAO,
)

retriever = vectorstore_consulta.as_retriever(search_kwargs={"k": 4})

# 2. Definição da Ferramenta (Tool Calling)
@tool
def buscar_normativa_ifpa(pergunta: str) -> str:
    """Busca trechos de documentos oficiais do IFPA relevantes para responder a uma pergunta sobre normas."""
    try:
        resultados = retriever.invoke(pergunta)
    except Exception as erro:
        return f"[ERRO NA BUSCA] Falha ao consultar a base vetorial: {erro}"

    if not resultados:
        return "Nenhum trecho relevante foi encontrado na base documental do IFPA para esta consulta."

    trechos = []
    for doc in resultados:
        fonte = os.path.basename(doc.metadata.get("source", "documento desconhecido"))
        pagina = doc.metadata.get("page", "?")
        trechos.append(f"[Fonte: {fonte}, página {pagina}]\n{doc.page_content}")

    return "\n\n---\n\n".join(trechos)

# 3. Configuração do LLM e Agente ReAct
SYSTEM_PROMPT = """Você é o Assistente Virtual Acadêmico do IFPA - Campus Ananindeua,
especializado em normas institucionais do curso de Bacharelado em Ciência da Computação.
REGRAS INVIOLÁVEIS:
1. Para QUALQUER pergunta sobre normas, resoluções ou calendários, você DEVE usar a ferramenta
   'buscar_normativa_ifpa' antes de responder.
2. Se a ferramenta não retornar informação, diga que não localizou nos documentos.
3. Toda resposta deve citar o nome do arquivo e a página de origem.
4. Respostas objetivas, em português, sem floreios."""

llm = ChatGoogleGenerativeAI(model="gemini-3.8-flash", temperature=0)

agente = create_react_agent(
    model=llm,
    tools=[buscar_normativa_ifpa],
    prompt=SYSTEM_PROMPT,
    checkpointer=InMemorySaver(),
)

# 4. Estrutura de Resposta Pydantic
class RespostaEstruturada(BaseModel):
    resposta: str = Field(description="Resposta objetiva em português.")
    documento_fonte: str = Field(description="Nome do PDF institucional usado como base. 'N/A' se não usado.")
    pagina: str = Field(description="Número da página. 'N/A' se não aplicável.")
    confianca: Literal["alta", "media", "baixa"] = Field(description="Confiança na resposta.")

llm_estruturado = llm.with_structured_output(RespostaEstruturada)

def gerar_resposta_estruturada(pergunta: str, resposta_bruta: str, contexto_recuperado: str) -> dict:
    prompt_formatacao = f"""Com base na pergunta, na resposta e no contexto, produza o JSON.
Pergunta: {pergunta}
Resposta do agente: {resposta_bruta}
Contexto: {contexto_recuperado[:2000]}"""
    
    try:
        resultado = llm_estruturado.invoke(prompt_formatacao)
        return resultado.model_dump()
    except Exception:
        try:
            saida_bruta = llm.invoke(prompt_formatacao + "\nResponda ESTRITAMENTE em JSON.").content
            return json.loads(repair_json(saida_bruta))
        except Exception:
            return {"resposta": resposta_bruta, "documento_fonte": "N/A", "pagina": "N/A", "confianca": "baixa"}

# 5. Configuração da API FastAPI
app = FastAPI(title="API Assistente Acadêmico IFPA")

class PerguntaUsuario(BaseModel):
    pergunta: str

@app.get("/")
def health_check():
    """Endpoint crucial para o deploy na nuvem saber que a API está viva."""
    return {"status": "200 OK", "mensagem": "API a correr perfeitamente."}

@app.post("/chat")
def chat_endpoint(payload: PerguntaUsuario):
    config = {"configurable": {"thread_id": "sessao_api"}}
    entrada = {"messages": [{"role": "user", "content": payload.pergunta}]}
    
    contexto_acumulado = ""
    resposta_final_texto = ""

    try:
        for evento in agente.stream(entrada, config, stream_mode="values"):
            ultima = evento["messages"][-1]
            if ultima.type == "tool":
                contexto_acumulado += ultima.content + "\n"
            elif ultima.type == "ai" and not getattr(ultima, "tool_calls", None):
                resposta_final_texto = ultima.content

        return gerar_resposta_estruturada(payload.pergunta, resposta_final_texto, contexto_acumulado)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))