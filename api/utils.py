import re
import os

def parse_chat(chat_file):
    SENDER_NAME = "."  # Replace with the actual name as it appears in the chat
    media_folder = os.path.dirname(chat_file)  # Directory where media is stored

    # Adjusted pattern to match text and media messages
    pattern = r"\[(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{1,2}:\d{1,2})(?:\s*|\u202F)?(AM|PM)?\] ([^:]+): (.+)"

    messages = []

    try:
        with open(chat_file, 'r', encoding='utf-8-sig') as f:
            for line in f:
                match = re.match(pattern, line)
                if match:
                    date, time, am_pm, sender, message = match.groups()
                    timestamp = f"{date} {time} {am_pm}".strip()
                    
                    # Mark messages from yourself as "You"
                    sender = "You" if sender == SENDER_NAME else sender.strip()

                    messages.append({
                        "timestamp": timestamp,
                        "sender": sender,
                        "message": message.strip(),
                        "media": None  
                    })
                elif "<attached:" in line:
                    media_file = line.split("<attached:")[1].strip(">\n").strip()  
                    
                    media_path = os.path.join(media_folder, media_file)

                    if messages:
                        messages[-1]["media"] = media_file  # Store just the file name without leading space
                        
    except FileNotFoundError:
        print(f"Error: The file {chat_file} was not found.")
    except Exception as e:
        print(f"An error occurred while parsing the chat file: {e}")

    return messages

