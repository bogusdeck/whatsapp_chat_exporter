import re

def parse_chat(chat_file):
    pattern = r"(\d{2}/\d{2}/\d{4}, \d{2}:\d{2}) - ([^:]+): (.+)"
    messages = []

    with open(chat_file, 'r', encoding='utf-8') as f:
        for line in f:
            match = re.match(pattern, line)
            if match:
                timestamp, sender, message = match.groups()
                messages.append({"timestamp": timestamp, "sender": sender, "message": message})
    
    return messages

