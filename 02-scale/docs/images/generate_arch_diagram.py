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

CHANGE 1 — CRITICAL: Find the text "VECTOR MEMORY" in the Platform Services bar at the bottom of the Agent Engine box. REPLACE the word "VECTOR MEMORY" with just the single word "MEMORY". Delete the word "VECTOR". The box should read "MEMORY" only. Do NOT keep the word "Vector".

CHANGE 2: The diagram already has ERP System and CRM System on the left — keep them exactly as they are.

Do NOT change anything else.""",
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
