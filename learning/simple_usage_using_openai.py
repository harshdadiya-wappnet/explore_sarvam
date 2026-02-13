from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

def main():

    print("Hello from explore-sarvam!")

    client = OpenAI(
        api_key=os.getenv("SARVAM_API_KEY"),
        base_url="http://localhost:8000" # change the default port if needed
    )

    while True:
        try:
            user_message = input("You: ").strip()
            if not user_message:
                continue
            if user_message.lower() in ("exit", "quit", "q"):
                print("Exiting.")
                break

            response = client.chat.completions.create(
                messages=[
                    {"content": "You are best help ai assistant helping user to solve thier complex", "role": "system"},
                    {"content": user_message, "role": "user"},
                ],
                model="sarvam-m"
            )
            ai_response = None
            for i in response.choices:
                if i.finish_reason == "stop":
                    ai_response = i.message.content
            print("AI:",ai_response)

        except KeyboardInterrupt:
            print("\nExiting.")
            break
    # print the top "choice" 
    # print(chat_completion.choices[0].message.content)



if __name__ == "__main__":
    main()
