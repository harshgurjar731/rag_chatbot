"""
VLM Captioner — Dense captioning using Mistral Large via Mistral API.

Takes selected frames and generates structured dense captions
describing the visual content of each video chunk.

Uses the Mistral Chat endpoint: https://api.mistral.ai/v1/chat/completions
"""

import base64
import logging
import time
from io import BytesIO

from PIL import Image

from .config import VLMConfig
from .models import CaptionResult

logger = logging.getLogger(__name__)


class VLMCaptioner:
    """Generates dense captions from video frames using Mistral Large via Mistral API."""

    CHAT_API_URL = "https://api.mistral.ai/v1/chat/completions"

    def __init__(self, config: VLMConfig, api_key: str = ""):
        self.config = config
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        """Lazily initialize the Mistral client."""
        if self._client is None:
            from mistralai import Mistral

            if not self.api_key:
                raise ValueError(
                    "MISTRAL_API_KEY not set. Provide it via the "
                    "MISTRAL_API_KEY environment variable."
                )
            self._client = Mistral(api_key=self.api_key)
        return self._client

    def _frame_to_base64(self, frame: Image.Image) -> str:
        """Convert a PIL image to a base64 data URI for Mistral vision."""
        buf = BytesIO()
        frame.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/jpeg;base64,{b64}"

    def caption_frames(self, frames: list[dict]) -> CaptionResult:
        """
        Generate a dense caption from a list of video frames.

        Args:
            frames: List of dicts from VideoProcessor.extract_frames(), each with:
                - "frame": PIL Image
                - "timestamp": float
                - "frame_index": int

        Returns:
            CaptionResult with the generated caption text.
        """
        if not frames:
            logger.warning("No frames provided for captioning")
            return CaptionResult(engine="mistral_api", model=self.config.model, text="")

        client = self._get_client()

        # Limit to configured frames per request with uniform sampling
        n = self.config.frames_per_request
        total = len(frames)
        if total <= n:
            selected_frames = frames
        else:
            if n > 1:
                indices = [int(i * (total - 1) / (n - 1)) for i in range(n)]
            else:
                indices = [total // 2]
            selected_frames = [frames[i] for i in indices]

        # Build timestamp context
        timestamp_info = ", ".join(
            [f"Frame {i+1}: {f['timestamp']:.1f}s" for i, f in enumerate(selected_frames)]
        )

        # Build content array with images + text prompt
        content = []

        # Add each frame as an image_url content part
        for f in selected_frames:
            data_uri = self._frame_to_base64(f["frame"])
            content.append({
                "type": "image_url",
                "image_url": data_uri,
            })

        # Add the text prompt
        prompt_text = f"Timestamps: {timestamp_info}\n\n{self.config.caption_prompt}"
        content.append({
            "type": "text",
            "text": prompt_text,
        })

        logger.info(
            f"Generating caption for {len(selected_frames)} frames "
            f"via Mistral API ({self.config.model})..."
        )

        # Retry with exponential backoff for rate limiting (free tier = 1 RPS)
        max_retries = 3
        base_delay = 2  # seconds

        for attempt in range(max_retries + 1):
            try:
                response = client.chat.complete(
                    model=self.config.model,
                    messages=[
                        {
                            "role": "user",
                            "content": content,
                        }
                    ],
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                )
                caption_text = response.choices[0].message.content.strip()
                break  # Success
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate_limit" in error_str.lower():
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            f"Rate limited (attempt {attempt + 1}/{max_retries + 1}). "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"Rate limited after {max_retries + 1} attempts")
                        raise RuntimeError(
                            f"Mistral VLM rate limited after {max_retries + 1} attempts"
                        ) from e
                else:
                    logger.error(f"Mistral VLM API call failed: {e}")
                    raise RuntimeError(f"Mistral VLM captioning failed: {e}") from e

        result = CaptionResult(
            engine="mistral_api",
            model=self.config.model,
            text=caption_text,
        )

        logger.info(f"Caption generated: {len(caption_text)} chars")
        return result
