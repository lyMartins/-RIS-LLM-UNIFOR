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
    """Formata uma string de valor para o padrão monetário brasileiro."""
    try:
        valor_limpo = re.sub(r'[^\d,]', '', str(valor_str)).replace(',', '.')
        valor_decimal = Decimal(valor_limpo)
        return f'{valor_decimal:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    except (InvalidOperation, TypeError):
        return valor_str


def enviar_prompt_para_bloco(texto_bloco: str) -> str:
    """Envia um bloco de decreto para o Gemini e retorna o JSON puro."""

    prompt = f"""
    Você é um assistente especialista em análise de decretos orçamentários municipais. 
    Seu objetivo é extrair informações precisas de textos que podem conter ruídos de OCR, múltiplas páginas ou formatações inconsistentes.
    Siga **rigorosamente** todas as instruções abaixo.

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

    <texto_decreto>
    {texto_bloco}
    </texto_decreto>
    """

    try:
        model = genai.GenerativeModel("models/gemini-pro-latest")
        response = model.generate_content(prompt)

        json_text = response.text.strip()
        json_text = re.sub(r"^```[jJ]?[sS]?[oO]?[nN]?", "", json_text).strip()
        json_text = re.sub(r"```$", "", json_text).strip()
        return json_text
    except Exception as e:
        print(f"⚠️ Erro na chamada da API do Gemini: {e}")
        return None


# --- LÓGICA PRINCIPAL ---
if __name__ == "__main__":
    arquivo_alvo = "decretos_fortim.txt"
    with open(arquivo_alvo, "r", encoding="utf-8") as f:
        texto_completo = f.read()

    print(f"🔪 Fatiando o documento '{arquivo_alvo}' em blocos de decretos...")
    # Linha corrigida, que torna " Orçamentário" opcional
    padrao_split = r'\n(?=DECRETO(?: Orçamentário)? Nº)'    
    blocos_decretos = re.split(padrao_split, texto_completo, flags=re.IGNORECASE)
    print(f"   {len(blocos_decretos)} blocos encontrados.")

    quadro1_total, quadro2_total, quadro3_total = [], [], []

    for i, bloco in enumerate(blocos_decretos):
        if not bloco.strip() or "Art. 1º" not in bloco or "Art. 2º" not in bloco:
            continue

        print(f"\n🧠 Analisando bloco {i + 1}/{len(blocos_decretos)}...")
        resposta_json_str = enviar_prompt_para_bloco(bloco)

        if resposta_json_str:
            try:
                dados = json.loads(resposta_json_str)
                if isinstance(dados, dict):
                    quadro1_total.extend(dados.get("quadro1", []))
                    quadro2_total.extend(dados.get("quadro2", []))
                    quadro3_total.extend(dados.get("quadro3", []))
                    print(f"   ✅ Bloco {i + 1} processado com sucesso.")
                else:
                    print(f"   ⚠️ JSON retornado não é um objeto esperado.")
            except json.JSONDecodeError:
                print(f"   ⚠️ Bloco {i + 1} não retornou um JSON válido.")

    print("\n" + "=" * 80)
    print(f"🎉 Extração concluída!")
    print("=" * 80)

    # --- Montagem dos DataFrames ---
    if quadro1_total:
        quadro1_df = pd.DataFrame(quadro1_total)
        if 'valor_total' in quadro1_df.columns:
            quadro1_df['valor_total'] = quadro1_df['valor_total'].apply(formatar_valor_brl)
            quadro1_df.rename(columns={'valor_total': 'valor do decreto'}, inplace=True)
        quadro1_df.to_csv("quadro1.csv", index=False, sep=';', encoding='utf-8-sig')
        print(f" - quadro1ver2.csv ({len(quadro1_df)} registros) salvo.")

    if quadro3_total:
        quadro3_df = pd.DataFrame(quadro3_total)
        quadro3_df.to_csv("quadro3.csv", index=False, sep=';', encoding='utf-8-sig')
        print(f" - quadro3ver2.csv ({len(quadro3_df)} registros) salvo.")
