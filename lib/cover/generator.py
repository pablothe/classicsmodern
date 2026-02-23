#!/usr/bin/env python3
"""
Cover Art Generation using Stable Diffusion

Generates AI-powered cover art for audiobooks using Stable Diffusion v1.5.
Runs locally on Apple Silicon GPU (MPS) or CPU fallback.

Requirements:
    pip install diffusers torch transformers accelerate
"""

from pathlib import Path


class CoverArtGenerator:
    """Generate AI cover art using Stable Diffusion"""

    DEFAULT_MODEL = "runwayml/stable-diffusion-v1-5"

    def __init__(self, model_id: str = DEFAULT_MODEL, device: str = "auto"):
        """
        Initialize Stable Diffusion pipeline.

        Args:
            model_id: HuggingFace model ID
            device: Device to run on ("mps", "cuda", "cpu", or "auto")
        """
        try:
            from diffusers import StableDiffusionPipeline
            import torch
        except ImportError:
            raise ImportError(
                "Cover generation requires: pip install diffusers torch transformers accelerate"
            )

        self.model_id = model_id

        # Auto-detect device
        if device == "auto":
            if torch.backends.mps.is_available():
                self.device = "mps"
            elif torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"
        else:
            self.device = device

        print(f"Loading Stable Diffusion model: {model_id}")
        print(f"Device: {self.device}")

        # Load pipeline
        dtype = torch.float16 if self.device in ["mps", "cuda"] else torch.float32

        self.pipe = StableDiffusionPipeline.from_pretrained(
            model_id,
            torch_dtype=dtype
        )

        self.pipe.to(self.device)
        print("✓ Model loaded successfully")

    def generate_cover(
        self,
        prompt: str,
        output_path: str,
        guidance_scale: float = 7.5,
        num_inference_steps: int = 50,
        width: int = 512,
        height: int = 512
    ) -> Path:
        """
        Generate cover art from text prompt.

        Args:
            prompt: Text description of desired image
            output_path: Where to save the generated image
            guidance_scale: How closely to follow the prompt (7.5 default)
            num_inference_steps: Quality/speed tradeoff (50 default)
            width: Image width in pixels (512 default)
            height: Image height in pixels (512 default)

        Returns:
            Path to generated image
        """
        print(f"\nGenerating image...")
        print(f"Prompt: {prompt}")
        print(f"Size: {width}x{height}")
        print(f"Guidance scale: {guidance_scale}")
        print(f"Steps: {num_inference_steps}")

        # Generate image
        image = self.pipe(
            prompt,
            guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps,
            width=width,
            height=height
        ).images[0]

        # Save image
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(output_path))

        print(f"✓ Image saved: {output_path}")
        return output_path


def generate_image(
    prompt: str,
    output_path: str,
    width: int = 512,
    height: int = 512,
    num_inference_steps: int = 30,
    guidance_scale: float = 7.5
) -> Path:
    """Convenience function wrapping CoverArtGenerator for CLI scripts."""
    generator = CoverArtGenerator()
    return generator.generate_cover(
        prompt=prompt,
        output_path=output_path,
        width=width,
        height=height,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
    )


def main():
    """Command-line interface for cover art generation"""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Generate AI cover art for audiobooks using Stable Diffusion"
    )

    parser.add_argument(
        "prompt",
        type=str,
        help="Text description for image generation"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="cover.png",
        help="Output image path (default: cover.png)"
    )

    parser.add_argument(
        "--model",
        type=str,
        default=CoverArtGenerator.DEFAULT_MODEL,
        help=f"Stable Diffusion model ID (default: {CoverArtGenerator.DEFAULT_MODEL})"
    )

    parser.add_argument(
        "--guidance-scale",
        type=float,
        default=7.5,
        help="Guidance scale (default: 7.5)"
    )

    parser.add_argument(
        "--steps",
        type=int,
        default=50,
        help="Number of inference steps (default: 50)"
    )

    parser.add_argument(
        "--width",
        type=int,
        default=512,
        help="Image width (default: 512)"
    )

    parser.add_argument(
        "--height",
        type=int,
        default=512,
        help="Image height (default: 512)"
    )

    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "mps", "cuda", "cpu"],
        help="Device to run on (default: auto)"
    )

    args = parser.parse_args()

    try:
        # Initialize generator
        generator = CoverArtGenerator(
            model_id=args.model,
            device=args.device
        )

        # Generate image
        output_path = generator.generate_cover(
            args.prompt,
            args.output,
            guidance_scale=args.guidance_scale,
            num_inference_steps=args.steps,
            width=args.width,
            height=args.height
        )

        print(f"\n✅ Success! Cover art generated: {output_path}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
