import json
import os
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv

# --- Configurações Seguras ---
# 1. Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# 2. Configura a API usando a chave carregada do ambiente
# A biblioteca vai procurar automaticamente pela variável GOOGLE_API_KEY
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("A variável GOOGLE_API_KEY não foi encontrada. Verifique seu arquivo .env.")
genai.configure(api_key=api_key)

ARQUIVO_DECRETOS = "decretos_fortim.txt"


# Função para enviar prompt ao Gemini (usando a API moderna)
def enviar_prompt(texto_do_documento: str) -> str:
    # O seu prompt, mantido exatamente como você escreveu, pois está perfeito.
    prompt = f"""
    Você é um assistente especialista em análise de decretos orçamentários municipais. Seu objetivo é extrair informações precisas de textos que podem conter ruídos, documentos em múltiplas páginas, ou formatos variados. Siga estas instruções rigorosamente.

    <texto_documento>
    {texto_do_documento}
    </texto_documento>

    Com base no texto acima, extraia as seguintes informações:

    1️⃣ **Critérios de seleção de documentos**:
    - Considere como 'decreto' apenas os documentos que começam com a palavra "DECRETO" seguida de número e data.
    - O decreto deve conter obrigatoriamente os Artigos Primeiro e Segundo.
    - Ignore qualquer documento que comece com "LEI", "OFÍCIO" ou "OFICIO".

    2️⃣ **Informações a extrair**:
    - "numero_decreto": Número do decreto.
    - "data_decreto": Data do decreto.
    - "valor_decreto": Valor do crédito adicional (extraia do Artigo 1º).
    - "tipo_credito": Tipo de crédito adicional ("Créditos Suplementares", "Créditos Especiais" ou "Créditos Extraordinários").
    - "fonte_recurso": Fonte de recurso do crédito adicional (do Artigo 2º). Possíveis valores: "Superávit Financeiro", "Excesso de Arrecadação", "Anulação de Dotações" e/ou "Operações de Crédito".
    - "codigo_fonte": Se a fonte for "Excesso de Arrecadação", extraia o código de 10 dígitos associado.

    3️⃣ **Regras de interpretação**:
    - Artigo 1º: 'Crédito Suplementar', 'Crédito Adicional Suplementar', etc., devem ser "Créditos Suplementares".
    - Artigo 2º: 'Anulação de Dotações', 'Anulações Parciais...', etc., devem ser "Anulação de Dotações".

    4️⃣ **Formato de saída**:
    - Retorne **somente um único objeto JSON válido**. A raiz do objeto deve conter uma chave "decretos", que é uma lista de todos os decretos encontrados.
    - Cada item na lista "decretos" deve ser um objeto JSON com as informações extraídas.
    - Exemplo de objeto JSON:
    ```json
    {{
      "decretos": [
        {{
          "numero_decreto": "08/2023",
          "data_decreto": "1 de Agosto de 2023",
          "valor_decreto": "2.041.680,00",
          "tipo_credito": "Créditos Suplementares",
          "fonte_recurso": "Anulação de Dotações",
          "codigo_fonte": null
        }}
      ]
    }}
    ```
    """

    # Usando a API moderna: GenerativeModel e generate_content
    model = genai.GenerativeModel('gemini-pro-latest')  # Ou o modelo que preferir da sua lista
    response = model.generate_content(prompt)

    # Limpa a saída do modelo para garantir que é apenas o JSON
    json_text = response.text.strip().replace("```json", "").replace("```", "")
    return json_text


# Função para carregar e limpar JSON (sem alterações)
def parse_json(json_text):
    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"❌ Erro ao converter JSON: {e}")
        print(f"   Texto recebido do modelo:\n{json_text}")
        return None


# -------- Lógica principal --------
if __name__ == "__main__":
    with open(ARQUIVO_DECRETOS, "r", encoding="utf-8") as f:
        texto = f.read()

    print("🧠 Enviando texto para análise do Gemini...")
    resposta_json = enviar_prompt(texto)

    if not resposta_json:
        print("❌ O modelo não retornou uma resposta.")
        exit(1)

    parsed = parse_json(resposta_json)
    if parsed is None or "decretos" not in parsed:
        print("❌ A resposta do modelo não continha a estrutura JSON esperada (chave 'decretos').")
        exit(1)

    # Transformar os dados em DataFrames
    todos_decretos = parsed.get("decretos", [])

    quadro1 = pd.DataFrame(todos_decretos)

    # Lógica para Quadro 2 (Múltiplas Fontes) - Se necessário no futuro
    # quadro2 = ...

    # Lógica para Quadro 3 (Excesso de Arrecadação)
    quadro3 = quadro1[quadro1['fonte_recurso'] == 'Excesso de Arrecadação'].copy()

    # Salvar os DataFrames em arquivos CSV
    quadro1.to_csv("quadro1.csv", index=False, sep=';', encoding='utf-8-sig')
    quadro3.to_csv("quadro3.csv", index=False, sep=';', encoding='utf-8-sig')

    print("✅ Extração concluída. Quadros salvos como CSV:")
    print(f" - quadro1ver1.csv ({len(quadro1)} registros)")
    print(f" - quadro3ver1.csv ({len(quadro3)} registros)")