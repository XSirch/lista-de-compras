import asyncio
import re
import json
import pandas as pd
from dotenv import load_dotenv

from browser_use import Agent, BrowserSession
from browser_use.llm import ChatOpenAI

load_dotenv()

PROMPT = """
Você é um agente especializado em sourcing industrial no Brasil.
Para cada item informado, execute o seguinte:
1. Busque no Google (resultados naturais) com o nome completo + especificações.
2. Verifique os 3 primeiros resultados relevantes:
   a. Acesse a página e identifique preço em Reais (ex: "R$ 12.345,67").
   b. Identifique nome da loja e URL.
3. Situações:
   - Se **nenhum resultado relevante** → JSON: {"status":"item não encontrado"}.
   - Se encontrou produtos mas **sem preço visível**, retorne: {"status":"produto encontrado sem preço, entre em contato com o fornecedor: <nome da loja>"}.
   - Se encontrou preços, retorne o menor:
     {"status":"preço encontrado", "preço": 1234.56, "loja":"<nome>", "url":"<url>"}.
4. Use apenas fontes brasileiras ou que entreguem no Brasil.

Retorne **exatamente** um objeto JSON por item.
"""

CONCURRENCY =  1 # Quantos itens pesquisar em paralelo (ajuste conforme sua banda e recursos)

async def buscar_preco(agent, prompt, item):
    agent.task = prompt + f"\nItem: \"{item}\""
    try:
        resposta = await agent.run()
        data = re.search(r"\{.*\}", resposta, re.DOTALL).group(0)
        obj = json.loads(data)
        return obj
    except Exception as e:
        return {"status": f"erro: {str(e)}"}

async def processar_lote(df, agent, prompt, indices):
    results = []
    tasks = []
    for i in indices:
        item = df.at[i, 'Item']
        print(f"🔍 [#{i}] Buscando: {item}")
        tasks.append(buscar_preco(agent, prompt, item))
    chunk_results = await asyncio.gather(*tasks)
    for idx, obj in zip(indices, chunk_results):
        df.at[idx, 'status'] = obj.get("status")
        if obj.get("status") == "preço encontrado":
            df.at[idx, 'preço'] = obj.get("preço")
            df.at[idx, 'loja'] = obj.get("loja")
            df.at[idx, 'url'] = obj.get("url")
        else:
            df.at[idx, 'loja'] = obj.get("loja", "")
            df.at[idx, 'url'] = obj.get("url", "")
    return df

async def buscar_precos(input_file: str, output_file: str):
    df = pd.read_excel(input_file).head(2)
    df['status'] = None
    df['preço'] = None
    df['loja'] = None
    df['url'] = None

    browser_session = BrowserSession(
        headless=True,
        viewport={'width': 964, 'height': 647},
        user_data_dir='~/.config/browseruse/profiles/default',
)

    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
    agent = Agent(task=PROMPT, llm=llm, browser_session=browser_session)

    # Multi-concorrência por lotes
    indices = list(df.index)
    for i in range(0, len(indices), CONCURRENCY):
        chunk = indices[i:i+CONCURRENCY]
        df = await processar_lote(df, agent, PROMPT, chunk)
        await asyncio.sleep(2)  # Pausa entre os lotes

    # Salvar resultados
    df.to_excel(output_file, index=False)
    await browser_session.close()
    print(f"✅ Concluído. Arquivo salvo em: {output_file}")

if __name__ == "__main__":
    asyncio.run(buscar_precos(
        "Lista_Compras_Enxoval_Agile_Categorizada.xlsx",
        "Lista_Compras_com_Precos_Agente.xlsx"
    ))
