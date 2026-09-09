import datetime
import random
import math
import json
import os


# =========================
# BOT CONFIGURATION
# =========================

BOT_NAME = "Nova"

MEMORY_FILE = "memory.json"


# =========================
# MEMORY SYSTEM
# =========================

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as file:
            return json.load(file)

    return {
        "name": None,
        "facts": []
    }


def save_memory(memory):
    with open(MEMORY_FILE, "w") as file:
        json.dump(memory, file, indent=4)


memory = load_memory()


# =========================
# UTILITY FUNCTIONS
# =========================

def get_time():
    now = datetime.datetime.now()
    return now.strftime("%I:%M %p")


def get_date():
    now = datetime.datetime.now()
    return now.strftime("%d %B %Y")


def calculate(expression):
    try:
        # Basic mathematical functions
        allowed = {
            "sqrt": math.sqrt,
            "pow": pow,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "pi": math.pi,
            "e": math.e
        }

        result = eval(expression, {"__builtins__": {}}, allowed)

        return result

    except Exception:
        return None


# =========================
# RESPONSE SYSTEM
# =========================

def get_response(user_input):

    text = user_input.lower().strip()

    # -------------------------
    # Greetings
    # -------------------------

    if text in ["hello", "hi", "hey", "hii"]:
        return random.choice([
            f"Hello! 👋 Main {BOT_NAME} hoon.",
            "Hey! Kaise ho? 😊",
            "Hi! Main tumhari help ke liye ready hoon."
        ])

    # -------------------------
    # Bot identity
    # -------------------------

    if "your name" in text or "tumhara naam" in text:
        return f"Mera naam {BOT_NAME} hai 🤖"

    if "who are you" in text or "tum kaun ho" in text:
        return (
            f"Main {BOT_NAME} hoon — ek advanced Python chatbot. "
            "Main calculations, memory, date/time aur commands handle kar sakta hoon."
        )

    # -------------------------
    # Time
    # -------------------------

    if "time" in text or "samay" in text:
        return f"Abhi time hai {get_time()} ⏰"

    # -------------------------
    # Date
    # -------------------------

    if "date" in text or "tarikh" in text:
        return f"Aaj ki date hai {get_date()} 📅"

    # -------------------------
    # User name
    # -------------------------

    if text.startswith("my name is "):
        name = user_input[11:].strip()

        if name:
            memory["name"] = name
            save_memory(memory)

            return f"Nice to meet you, {name}! 😊 Main tumhara naam yaad rakhunga."

    if "what is my name" in text or "mera naam kya hai" in text:

        if memory["name"]:
            return f"Tumhara naam {memory['name']} hai. 😎"

        return "Tumne abhi tak mujhe apna naam nahi bataya."

    # -------------------------
    # Remember information
    # -------------------------

    if text.startswith("remember "):

        fact = user_input[9:].strip()

        if fact:
            memory["facts"].append(fact)
            save_memory(memory)

            return "Okay 👍 Maine ye information yaad rakh li."

    # -------------------------
    # Show memory
    # -------------------------

    if "what do you remember" in text:

        if not memory["facts"]:
            return "Abhi meri memory empty hai."

        return "Mujhe ye yaad hai:\n- " + "\n- ".join(memory["facts"])

    # -------------------------
    # Calculator
    # -------------------------

    if text.startswith("calculate "):

        expression = user_input[10:].strip()

        result = calculate(expression)

        if result is not None:
            return f"Answer = {result} 🧮"

        return "Sorry, calculation samajh nahi aayi."

    # -------------------------
    # Help
    # -------------------------

    if text == "help":

        return """
Available commands:

1. hello
2. what is your name
3. what is the time
4. what is today's date
5. my name is Monu
6. what is my name
7. remember I like Python
8. what do you remember
9. calculate 25 * 10
10. clear memory
11. help
12. bye
"""

    # -------------------------
    # Clear memory
    # -------------------------

    if text == "clear memory":

        memory["name"] = None
        memory["facts"] = []

        save_memory(memory)

        return "Memory successfully clear kar di 🧹"

    # -------------------------
    # Thanks
    # -------------------------

    if "thank" in text or "thanks" in text:

        return random.choice([
            "You're welcome! 😊",
            "Koi baat nahi! 👍",
            "Anytime! 🤖"
        ])

    # -------------------------
    # Default response
    # -------------------------

    return (
        "Hmm 🤔 mujhe iska exact answer nahi pata. "
        "Try 'help' to see what I can do."
    )


# =========================
# MAIN CHAT LOOP
# =========================

def start_bot():

    print("=" * 50)
    print(f"🤖 {BOT_NAME} AI CHATBOT")
    print("=" * 50)

    print("Type 'help' to see available commands.")
    print("Type 'bye' to exit.\n")

    while True:

        user_input = input("You: ")

        if user_input.lower().strip() == "bye":

            print(f"{BOT_NAME}: Bye! 👋 See you later.")
            break

        response = get_response(user_input)

        print(f"{BOT_NAME}: {response}")


# =========================
# START PROGRAM
# =========================

if __name__ == "__main__":
    start_bot()