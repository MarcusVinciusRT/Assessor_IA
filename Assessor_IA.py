from dotenv import load_dotenv
import os
import google.generativeai as genai
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
 
llm = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    system_instruction= "Isso é um problema de lógica, que a resposta pode não ser retirada hierarquicamente. Considere outros exemplos: Igor = Irmão, Diogo = Primo, Eva = Mãe",
    generation_config= genai.types.GenerationConfig(
        temperature= 0.7,
        top_p= 0.95
        #'stop_sequences': Para que serve 
        #'max_output_tokens': Para que serve
    )
)

user_prompt = """Se ARI é meu pai e BRUNO é meu primo, então CAROLINA é minha:
a) Mãe
b) Prima
c) Tia
d) Sobrinha
e) Irmã"""
 
try:
    response = llm.generate_content(user_prompt)
    print (response.text)
except Exception as e:
    print("Erro ao consumir a API:", e)