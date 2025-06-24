import requests

API_KEY = {YOUR_API_KEY}
API_URL = {YOUR_API_URL}
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def ask_mistral(question, context_docs):
    context = "\n\n".join(context_docs)
    prompt = f"""  You are a helpful assistant. Only answer using the provided context.
Do not use prior knowledge. If the answer is not present in the context,
respond with: 'This question is not covered in my knowledge base.'

{context}

{question}

**Answer**:
"""
    payload = {
        "model": "mistral-small",
        "messages": [{"role": "user", "content": prompt}]
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()["choices"][0]["message"]["content"]
