# analisador.py (Versão Definitiva com os 3 Quadros)

import os
import re
import json
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv
from decimal import Decimal, InvalidOperation

# --- CONFIGURAÇÃO SEGURA DA API ---
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("A variável GOOGLE_API_KEY não foi encontrada. Verifique seu arquivo .env.")
genai.configure(api_key=api_key)


# --- FUNÇÕES AUXILIARES ---
def formatar_valor_brl(valor_str: str) -> str:
    try:
        valor_limpo = re.sub(r'[^\d,]', '', str(valor_str)).replace(',', '.')
        valor_decimal = Decimal(valor_limpo)
        return f'{valor_decimal:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    except (InvalidOperation, TypeError):
        return valor_str


def enviar_prompt_para_bloco(texto_bloco: str) -> str:
    prompt = f"""
    Você é um assistente especialista em análise de decretos orçamentários. Sua tarefa é analisar o texto de um único decreto fornecido abaixo e retornar suas informações em um formato JSON estruturado.

    <texto_decreto>
    {texto_bloco}
    </texto_decreto>

    REGRAS DE EXTRAÇÃO:
    1.  **Critérios de Seleção**: Analise apenas se o documento for um "DECRETO" com "Artigo primeiro" e "Artigo segundo". Ignore "LEI" ou "OFÍCIO".

    2.  **Informações a Extrair**:
        - "numero_decreto": O número e ano do decreto (ex: "13/2023").
        - "data_decreto": A data por extenso (ex: "28 de Dezembro de 2023").
        - "valor_total": O valor total do crédito do Artigo 1º, retornado como um número float (ex: 1884373.30).
        - "tipo_credito": Normalize para "Créditos Suplementares", "Créditos Especiais" ou "Créditos Extraordinários".
        - "fontes": **Uma lista de objetos**, um para cada fonte de recurso encontrada no Artigo 2º.
            - Se o Artigo 2º tiver incisos com valores, crie um objeto para cada inciso.
            - Se for apenas no caput, crie um único objeto na lista.
            - Cada objeto na lista "fontes" deve conter:
                - "nome_da_fonte": Normalize para "Anulação de Dotações", "Excesso de Arrecadação", "Superávit Financeiro" ou "Operações de Crédito".
                - "valor_da_fonte": O valor específico para essa fonte, se detalhado no Artigo 2º (retornar como float). Se não houver valor específico, pode usar o valor total do decreto.
                - "codigo_fonte": Se a fonte for "Excesso de Arrecadação", extraia o código de 10 dígitos. Caso contrário, retorne null.

    3.  **Formato de Saída**:
        - Retorne **SOMENTE UM ÚNICO OBJETO JSON VÁLIDO**.
        - A raiz do objeto deve ter uma chave "decretos", que conterá uma lista com o único decreto analisado.
        - **Exemplo de Saída para um decreto com MÚLTIPLAS FONTES (importante para o Quadro 2):**
        ```json
        {{
          "decretos": [
            {{
              "numero_decreto": "12/2023",
              "data_decreto": "01 de Dezembro de 2023",
              "valor_total": 7176857.26,
              "tipo_credito": "Créditos Suplementares",
              "fontes": [
                {{
                  "nome_da_fonte": "Anulação de Dotações",
                  "valor_da_fonte": 4942314.23,
                  "codigo_fonte": null
                }},
                {{
                  "nome_da_fonte": "Superávit Financeiro",
                  "valor_da_fonte": 2234543.03,
                  "codigo_fonte": null
                }}
              ]
            }}
          ]
        }}
        ```
    """
    try:
        # ... (o resto da função continua igual)
        model = genai.GenerativeModel("models/gemini-pro-latest")
        response = model.generate_content(prompt)
        json_text = response.text.strip().replace("```json", "").replace("```", "")
        return json_text
    except Exception as e:
        print(f"   ⚠️ Erro na chamada da API do Gemini: {e}")
        return None


# --- LÓGICA PRINCIPAL ---
if __name__ == "__main__":
    arquivo_alvo = "decretos_hidrolandia2.txt"
    with open(arquivo_alvo, "r", encoding="utf-8") as f:
        texto_completo = f.read()

    print(f"🔪 Fatiando o documento '{arquivo_alvo}' em blocos de decretos...")
    padrao_split = r'\n(?=DECRETO(?: Orçamentário)?\s+N[º°]\.?)'
    blocos_decretos = re.split(padrao_split, texto_completo, flags=re.IGNORECASE)
    if not blocos_decretos[0].strip(): blocos_decretos.pop(0)
    print(f"   {len(blocos_decretos)} blocos encontrados.")

    lista_final_decretos = []

    for i, bloco in enumerate(blocos_decretos):
        if not bloco.strip() or not re.search(r'Art\.\s*1[º°o]', bloco, re.IGNORECASE) or not re.search(r'Art\.\s*2[º°o]', bloco, re.IGNORECASE):
            continue

        print(f"\n🧠 Analisando bloco {i + 1}/{len(blocos_decretos)}...")
        resposta_json_str = enviar_prompt_para_bloco(bloco)

        if resposta_json_str:
            try:
                dados = json.loads(resposta_json_str)
                if "decretos" in dados and isinstance(dados["decretos"], list):
                    lista_final_decretos.extend(dados["decretos"])
                    print(f"   ✅ Decreto(s) extraído(s) com sucesso.")
                else:
                    print(f"   ⚠️ Bloco {i + 1} retornou JSON, mas sem a chave 'decretos'.")
            except json.JSONDecodeError:
                print(f"   ⚠️ Bloco {i + 1} não retornou um JSON válido.")

    print("\n" + "=" * 80)
    print(f"🎉 Análise de todos os blocos concluída! Total de {len(lista_final_decretos)} decretos extraídos.")
    print("=" * 80)

    if lista_final_decretos:
        # --- Montagem dos Quadros ---
        q1_linhas, q2_linhas, q3_linhas = [], [], []

        for dec in lista_final_decretos:
            fontes = dec.get('fontes', [])
            nomes_fontes = sorted(list(set([f.get('nome_da_fonte') for f in fontes if f.get('nome_da_fonte')])))

            q1_linhas.append({
                "número do decreto": dec.get('numero_decreto'),
                "data do decreto": dec.get('data_decreto'),
                "valor do decreto": formatar_valor_brl(dec.get('valor_total')),
                "Tipo de Crédito Adicional": dec.get('tipo_credito'),
                "fonte de recurso do crédito adicional": ", ".join(nomes_fontes)
            })

            if len(fontes) > 1:
                for fonte in fontes:
                    q2_linhas.append({
                        "número do decreto": dec.get('numero_decreto'),
                        "data do decreto": dec.get('data_decreto'),
                        "valor do crédito adicional para cada fonte de recurso": formatar_valor_brl(
                            fonte.get('valor_da_fonte')),
                        "fonte de recurso do crédito adicional": fonte.get('nome_da_fonte')
                    })

            for fonte in fontes:
                if fonte.get('nome_da_fonte') == "Excesso de Arrecadação":
                    q3_linhas.append({
                        "número do decreto": dec.get('numero_decreto'),
                        "data do decreto": dec.get('data_decreto'),
                        "fonte de recurso do crédito adicional": fonte.get('nome_da_fonte'),
                        "código da fonte": fonte.get('codigo_fonte') or 'Não encontrado'
                    })

        quadro1_df = pd.DataFrame(q1_linhas)
        quadro2_df = pd.DataFrame(q2_linhas)
        quadro3_df = pd.DataFrame(q3_linhas)

        quadro1_df.to_csv("quadro1ver3.csv", index=False, sep=';', encoding='utf-8-sig')
        quadro2_df.to_csv("quadro2ver3.csv", index=False, sep=';', encoding='utf-8-sig')
        quadro3_df.to_csv("quadro3ver3.csv", index=False, sep=';', encoding='utf-8-sig')

        print("\n✅ Extração finalizada. Quadros salvos como CSV:")
        print(f" - quadro1ver3.csv ({len(quadro1_df)} registros)")
        print(f" - quadro2ver3.csv ({len(quadro2_df)} registros)")
        print(f" - quadro3ver3.csv ({len(quadro3_df)} registros)")