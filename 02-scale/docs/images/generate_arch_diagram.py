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
        "original_image.jpg",
    )
    with open(source_image_path, "rb") as f:
        image_data = f.read()

    response = client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=[
            Part.from_bytes(data=image_data, mime_type="image/jpeg"),
            """Edit this architecture diagram. Keep the same visual style and color scheme. Use LARGE, BOLD, clearly readable text for all labels — the text should be the same size as in the original image. Output a HIGH RESOLUTION image. Make these changes:

1. DELETE the "ERP System" box, the "CRM System" box, their database cylinder icons, and the "Model Context Protocol (MCP)" box on the far LEFT side of the diagram. Replace that entire left area with empty white space. Nothing should remain on the left side outside the Agent Engine boundary.
2. Inside the Execution Crew box, DELETE the "Customer Support Agent (Mocked, via CRM MCP)" block entirely. Keep only "Logistics Execution Crew (CrewAI)".
4. Keep the "ADK 2.0 Control Room Agent", the "Planning Agent (LangGraph)", and the "Execution Crew (CrewAI)" ALL INSIDE the Agent Engine boundary. They all run on Agent Engine.
5. Change the "ADK 2.0 Control Room Agent" box color from yellow/gold to the SAME purple/violet color used by the Planning Agent and Execution Crew boxes, so all three agent boxes use a consistent purple color scheme.
6. REARRANGE the layout inside the Agent Engine boundary into three rows:
   - TOP ROW: "ADK 2.0 Control Room Agent" centered at the top of the Agent Engine box.
   - MIDDLE ROW: "A2A Web Server (Uvicorn)" in the center, with "Planning Agent (LangGraph)" on the left and "Execution Crew (CrewAI)" on the right. Keep the arrows between them.
   - BOTTOM ROW: A horizontal bar labeled "Platform Services" spanning the full width, containing "Vector Memory", "Sessions", and "Batch Inference Jobs" side by side. Rename its title from "Agent Engine (Core Runtime)" to "Platform Services".
7. Keep the A2A Web Server (Uvicorn), External Systems & Tools on the right (Mercari Product Vector Store and Mock Order Management System), the Security Enforcement arrow, and the bottom identity bar exactly as they are.

IMPORTANT: Make all text large and legible. The diagram should fill the entire image canvas.""",
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
