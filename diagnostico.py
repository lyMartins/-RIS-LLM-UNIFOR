# Nome do arquivo: teste_api_correto.py

import os
import google.generativeai as genai
from dotenv import load_dotenv

# Carrega a NOVA chave do seu arquivo .env
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

try:
    print("Tentando se comunicar com o modelo Gemini (versão moderna)...")

    # Usando um nome de modelo que sabemos que existe na sua lista
    model = genai.GenerativeModel("models/gemini-pro-latest")

    response = model.generate_content("Olá, teste de conexão")

    print("✅ SUCESSO!")
    print(response.text)

except Exception as e:
    print(f"❌ FALHA: {e}")