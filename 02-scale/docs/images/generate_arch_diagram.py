import os
from io import BytesIO

from google import genai
from google.genai.types import GenerateContentConfig, Modality, Part
from PIL import Image


def generate():
    client = genai.Client()

    # Load the source image
    source_image_path = os.path.join(
        os.path.dirname(__file__),
        "scale-arch-diagram-updated.png",
    )
    with open(source_image_path, "rb") as f:
        image_data = f.read()

    response = client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=[
            Part.from_bytes(data=image_data, mime_type="image/jpeg"),
            """Edit this architecture diagram. Keep the same visual style and color scheme. Use LARGE, BOLD, clearly readable text. Output a HIGH RESOLUTION image.

Remove these parenthetical labels from the diagram text. Delete ONLY the parenthetical part, keep the main label:
- "(Core Runtime)" — delete everywhere
- "(Python)" — delete everywhere
- "(Uvicorn)" — delete everywhere
- "(CrewAI)" — delete everywhere EXCEPT in "Execution Crew (CrewAI)" which should KEEP "(CrewAI)"
- "(REST API)" — delete everywhere
- "(MCP tool)" — delete everywhere
- "(CrewAI, Python)" — replace with "(CrewAI)"
- "(aiplatform editor IAM)" or "(aiplatform.editor IAM)" — replace with "(Editor IAM)"

Do NOT change anything else. Keep all layout, colors, arrows, and other text exactly as they are.""",
        ],
        config=GenerateContentConfig(
            response_modalities=[Modality.TEXT, Modality.IMAGE],
            image_config=genai.types.ImageConfig(
                image_size="1K",
            ),
        ),
    )

    output_dir = os.path.dirname(__file__) or "."
    for part in response.candidates[0].content.parts:
        if part.text:
            print(part.text)
        elif part.inline_data:
            image = Image.open(BytesIO(part.inline_data.data))
            output_path = os.path.join(output_dir, "scale-arch-diagram-updated.png")
            image.save(output_path)
            print(f"File saved to: {output_path}")


if __name__ == "__main__":
    generate()
