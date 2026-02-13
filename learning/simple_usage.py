import os
from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()

client = SarvamAI(
    api_subscription_key=os.getenv("SARVAM_API_KEY"),
)

print("Type 'exit' or 'quit' to stop.")
while True:
    try:
        user_message = input("You: ").strip()
        if not user_message:
            continue
        if user_message.lower() in ("exit", "quit", "q"):
            print("Exiting.")
            break

        response = client.chat.completions(
            messages=[
                {"content": "You are best help ai assistant helping user to solve thier complex", "role": "system"},
                {"content": user_message, "role": "user"},
            ],
        )

        ai_response = None
        for i in response.choices:
            if i.finish_reason == "stop":
                ai_response = i.message.content
        print("AI:",ai_response)

    except KeyboardInterrupt:
        print("\nExiting.")
        break
