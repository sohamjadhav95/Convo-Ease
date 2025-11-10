from groq import Groq

API_KEY = input("Enter API Key = ")

system_message = input("Enter System Message : ")
user_message = input("Enter User Message : ")

while True:
    client = Groq(api_key=API_KEY)
    completion = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
        {
            "role": "system",
            "content": system_message
        },
        {
            "role": "user",
            "content": user_message
        }
        ],
        temperature=0.5,
        max_tokens=8192, 
        top_p=1,
        stream=True,
        stop=None
    )

    for chunk in completion:
        print(chunk.choices[0].delta.content or "", end="")
