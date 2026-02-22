import os
import openai
import base64
from dotenv import load_dotenv

# Load API key from .env file
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
client = openai.OpenAI(api_key=OPENAI_API_KEY)

def load_markdown_text(file_path):
    """Reads a Markdown file and returns its text content."""
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()

def generate_audio(text, output_file="output.wav", voice="alloy", format="wav"):
    """Generates audio from text using OpenAI's GPT-4o audio model."""
    response = client.chat.completions.create(
        model="gpt-4o-audio-preview",
        messages=[{"role": "user", "content": text}],
        modalities=["text", "audio"],
        audio={"voice": voice, "format": format},
        store=True,
    )

    # Extract and decode audio data
    audio_data = base64.b64decode(response.choices[0].message.audio.data)

    with open(output_file, "wb") as audio_file:
        audio_file.write(audio_data)

    print(f"Audio saved to {output_file}")

if __name__ == "__main__":
    input_markdown = "examples/alices_adventures_in_wonderland_chapter_1.md"  # Update path as needed
    output_audio = "output.wav"

    # Check if the file exists
    if not os.path.exists(input_markdown):
        print(f"Error: File not found: {input_markdown}")
        exit(1)

    text_content = load_markdown_text(input_markdown)
    generate_audio(text_content, output_audio)
