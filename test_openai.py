# test_openai.py
import os
from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI

print(f"API Key found: {'OPENAI_API_KEY' in os.environ}")

try:
    llm = ChatOpenAI()
    response = llm.invoke("Hello, how are you?")
    print("Success! Response:", response)
except Exception as e:
    print("Error:", str(e))