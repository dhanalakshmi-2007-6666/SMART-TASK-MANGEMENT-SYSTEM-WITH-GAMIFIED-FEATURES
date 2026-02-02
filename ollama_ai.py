import requests
import json

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


def ask_ai(prompt):
    try:
        payload = {
            "model": "llama3",   # make sure you pulled: ollama pull llama3
            "prompt": prompt,
            "stream": False
        }

        response = requests.post(OLLAMA_URL, json=payload)

        if response.status_code == 200:
            data = response.json()
            return data.get("response", "No response from AI.")
        else:
            return f"Error: {response.text}"

    except Exception as e:
        return f"Ollama connection error: {str(e)}"
