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
    Você é um assistente especialista em análise de decretos orçamentários municipais. 
    Seu objetivo é extrair informações precisas de textos que podem conter ruídos de OCR, múltiplas páginas ou formatações inconsistentes.
    Siga **rigorosamente** todas as instruções abaixo.
    
    <texto_decreto>
    {texto_bloco}
    </texto_decreto>

    🧹 **Etapa 0 – Limpeza e normalização do texto**
    - Corrija erros comuns de OCR.
    - Remova símbolos estranhos, repetições e ruídos como "(S)V", "VNISSV", "ASSHOV", etc.
    - Corrija separações indevidas de palavras.
    - Preserve apenas informações relacionadas a decretos, artigos e valores.

    ---

    ## 🧩 Etapa 1 – Critérios de seleção de documentos:
    - Considere como **decreto** apenas textos que **começam com "DECRETO"** seguido de **número e data**.
    - O documento deve conter **obrigatoriamente os Artigos 1º e 2º**.
    - Ignore textos que comecem com "LEI", "OFÍCIO" ou "OFICIO".

    ---

    ## 📋 Etapa 2 – Regras de interpretação dos artigos:
    - **Artigo 1º:** 
      - Localiza o valor do crédito adicional.
      - Termos como "Crédito Suplementar", "Crédito Adicional Suplementar", "Crédito Adicional" e "Suplementar" devem ser normalizados para **"Créditos Suplementares"**.
    - **Artigo 2º:** 
      - Indica a fonte de recurso.
      - Termos como "Anulação Parcial", "Anulações Parciais das Dotações Orçamentárias" e similares devem ser normalizados para **"Anulação de Dotações"**.
      - Pode conter fontes no caput ou detalhadas em incisos.

    ---

    ## 📊 Etapa 3 – Informações a extrair:
    ### **Quadro 1 – Resumo dos decretos** 
    | Campo | Descrição | 
    |--------|------------| | numero_decreto | Número do decreto (formato N/ANO) |
    | data_decreto | Data por extenso ou formato DD/MM/AAAA | 
    | valor_total | Valor do crédito do Artigo 1º, como número float |
    | tipo_credito | Tipo de crédito adicional ("Créditos Suplementares", "Créditos Especiais" ou "Créditos Extraordinários") |
    | fonte_recurso | Fonte de recurso do crédito (Artigo 2º) | | codigo_fonte |
     Código de 10 dígitos, apenas se a fonte for "Excesso de Arrecadação". Caso contrário, nulo. | 
    --- ### **Quadro 2 – Detalhamento por fonte de recurso** Cada fonte de recurso mencionada deve ser listada separadamente. 
    | Campo | Descrição | 
    |--------|------------| | numero_decreto | Número do decreto |
     | data_decreto | Data do decreto | 
     | valor_decreto | Valor correspondente a cada fonte | 
     | fonte_recurso | Nome da fonte (normalizado) | 
     --- 
     ### **Quadro 3 – Foco em 'Excesso de Arrecadação'** 
     Filtre **somente** decretos cuja fonte de recurso seja "Excesso de Arrecadação". 
     | Campo | Descrição | 
     |--------|------------| 
     | numero_decreto | Número do decreto | 
     | data_decreto | Data do decreto | 
     | fonte_recurso | Fonte de recurso | 
     | codigo_fonte | Código de 10 dígitos conforme PORTARIA Nº 710/2021 (formato XYYYZZZZ00) |

    ---

    ## 🧾 Etapa 4 – Formato de saída
    - Retorne **SOMENTE UM OBJETO JSON VÁLIDO**.
    - A raiz deve conter **"quadro1"**, **"quadro2"** e **"quadro3"**.
    - Não inclua texto fora do JSON.
    - Números no formato **float** com ponto decimal.
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
    arquivo_alvo = "decretos_hidrolandia4.txt"  # Você pode trocar para "fortim.txt" aqui
    try:
        with open(arquivo_alvo, "r", encoding="utf-8") as f:
            texto_completo = f.read()
    except FileNotFoundError:
        print(f"❌ ERRO FATAL: O arquivo '{arquivo_alvo}' não foi encontrado. Verifique o nome e o local do arquivo.")
        exit()

    print(f"🔪 Fatiando o documento '{arquivo_alvo}' em blocos de decretos...")
    # Padrão flexível para Fortim ('DECRETO Nº.') e Hidrolândia ('Decreto Orçamentário Nº')
    padrao_split = r'\n(?=DECRETO(?: Orçamentário)?\s+N[º°]\.?)'

    blocos_decretos = re.split(padrao_split, texto_completo, flags=re.IGNORECASE)
    if not blocos_decretos[0].strip():
        blocos_decretos.pop(0)
    print(f"   {len(blocos_decretos)} blocos encontrados.")

    lista_final_decretos = []

    for i, bloco in enumerate(blocos_decretos):
        # Filtro de validação do bloco
        if not bloco.strip() or not re.search(r'Art\.\s*1[º°o]', bloco, re.IGNORECASE) or not re.search(
                r'Art\.\s*2[º°o]', bloco, re.IGNORECASE):
            continue

        print(f"\n🧠 Analisando bloco {i + 1}/{len(blocos_decretos)}...")
        # Adicionamos "DECRETO " de volta para dar contexto ao LLM, já que o split removeu
        resposta_json_str = enviar_prompt_para_bloco("DECRETO " + bloco)

        try:
            dados = json.loads(resposta_json_str)
            if "quadro1" in dados and isinstance(dados["quadro1"], list) and len(dados["quadro1"]) > 0:
                lista_final_decretos.extend(dados["quadro1"])  # Pega os dados de 'quadro1'
                print(f"   ✅ Decreto(s) extraído(s) com sucesso.")
            else:
                # Atualizamos a mensagem de erro para refletir a nova lógica
                print(f"   ⚠️  Bloco {i + 1} retornou um JSON válido, mas está vazio ou sem a chave 'quadro1'.")
                print(
                    f"   ----------- RESPOSTA BRUTA DO MODELO -----------\n{resposta_json_str}\n   --------------------------------------------")
        except json.JSONDecodeError:
                # O texto retornado não é um JSON válido
                print(f"   ⚠️  Bloco {i + 1} não retornou um JSON válido.")
                print(
                    f"   ----------- RESPOSTA BRUTA DO MODELO -----------\n{resposta_json_str}\n   --------------------------------------------")

    print("\n" + "=" * 80)
    print(f"🎉 Análise de todos os blocos concluída! Total de {len(lista_final_decretos)} decretos extraídos.")
    print("=" * 80)

    if lista_final_decretos:
        # --- Montagem e salvamento dos Quadros ---
        # (Esta parte permanece a mesma, pois a lógica de criação das tabelas está correta)
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

        quadro1_df = pd.DataFrame(q1_linhas);
        quadro2_df = pd.DataFrame(q2_linhas);
        quadro3_df = pd.DataFrame(q3_linhas)
        quadro1_df.to_csv("quadro1ver4.csv", index=False, sep=';', encoding='utf-8-sig')
        quadro2_df.to_csv("quadro2ver4.csv", index=False, sep=';', encoding='utf-8-sig')
        quadro3_df.to_csv("quadro3ver4.csv", index=False, sep=';', encoding='utf-8-sig')

        print("\n✅ Extração finalizada. Quadros salvos como CSV:")
        print(f" - quadro1.csv ({len(quadro1_df)} registros)")
        print(f" - quadro2.csv ({len(quadro2_df)} registros)")
        print(f" - quadro3.csv ({len(quadro3_df)} registros)")