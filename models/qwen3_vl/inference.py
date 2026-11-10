"""Official Qwen3-VL Transformers inference, loaded once per run."""
from pathlib import Path


class QwenRunner:
    def __init__(self, model_path: Path, device: str = "auto"):
        import torch
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        self.torch = torch
        if device == "auto":
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        if device == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("MPS 不可用；请检查 Apple Silicon、macOS 和 PyTorch，或选择 --device cpu")
        self.device = device
        dtype = torch.float16 if device == "mps" else torch.float32
        self.processor = AutoProcessor.from_pretrained(str(model_path), local_files_only=True)
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            str(model_path), torch_dtype=dtype, local_files_only=True, low_cpu_mem_usage=True
        ).to(device).eval()

    def infer(self, prompt, image_path, max_new_tokens, on_input_tokens, on_generated):
        content = []
        if image_path:
            content.append({"type": "image", "image": str(image_path)})
        content.append({"type": "text", "text": prompt})
        messages = [{"role": "user", "content": content}]
        inputs = self.processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True,
            return_dict=True, return_tensors="pt"
        ).to(self.device)
        input_tokens = int(inputs["input_ids"].shape[-1])
        on_input_tokens(input_tokens)
        with self.torch.inference_mode():
            output = self.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        if self.device == "mps":
            self.torch.mps.synchronize()
        elif self.device == "cuda":
            self.torch.cuda.synchronize()
        generated = output[0, input_tokens:]
        output_tokens = int(generated.shape[-1])
        on_generated(output_tokens)
        answer = self.processor.decode(generated, skip_special_tokens=True, clean_up_tokenization_spaces=False)
        return answer
