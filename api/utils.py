import re
from datetime import datetime

def parse_chat(chat_file):
    from .index import ChatMessage
    pattern = r"\[(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{1,2}:\d{1,2})(?:\s*|\u202F)?(AM|PM)?\] ([^:]+): (.+)"
    messages = []
    count = 0
    current_message = None  # Store the ongoing message for multiline handling

    try:
        with open(chat_file, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()  # Remove trailing whitespace

                match = re.match(pattern, line)
                if match:
                    # If there was a previous message, add it to the messages list
                    if current_message:
                        messages.append(current_message)
                        count += 1

                    date, time, am_pm, sender, message = match.groups()

                    # Parse timestamp
                    try:
                        timestamp = datetime.strptime(
                            f"{date} {time} {am_pm}".strip(), 
                            "%d/%m/%y %I:%M:%S %p" if am_pm else "%d/%m/%y %H:%M:%S"
                        )
                    except ValueError:
                        print(f"Failed to parse: {date} {time} {am_pm}")
                        continue

                    # Mark messages from yourself as "You"
                    sender = "You" if sender == "." else sender.strip()

                    # Initialize the current message with data
                    current_message = ChatMessage(
                        timestamp=timestamp,
                        sender=sender,
                        message=message.strip(),
                        media=[],
                        media_urls=[]
                    )

                elif "<attached:" in line:
                    # Handle media attachments
                    media_file = line.split("<attached:")[1].strip(">\n").strip()
                    if current_message:
                        current_message.media.append(media_file)

                elif current_message:
                    # Handle multiline continuation
                    if line:
                        current_message.message += f"\n{line}"
                    else:
                        messages.append(current_message)
                        current_message = None  # Reset current_message for the next message

            # Add the last message if present
            if current_message:
                messages.append(current_message)
                count += 1

    except FileNotFoundError:
        print(f"Error: The file {chat_file} was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

    # Sort messages by timestamp (optional, as messages should already be in order)
    return sorted(messages, key=lambda x: x.timestamp), count
