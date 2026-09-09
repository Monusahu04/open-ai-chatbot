import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQQgsk_pkRbsWsUGX4K8wf2KqBKWGdyb3FYrJEsEtAHInpKe05g0KL1HvcO_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

print("🤖 AI Bot started! Type 'exit' to stop.")

while True:
    question = input("\nYou: ")

    if question.lower().strip() == "exit":
        print("Bot: Goodbye! 👋")
        break

    response = client.responses.create(
        model="openai/gpt-oss-20b",
        input=question
    )

    print("Bot:", response.output_text)