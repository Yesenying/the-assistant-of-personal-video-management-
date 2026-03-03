import numpy as np
import torch
from transformers import AutoProcessor, XCLIPModel

MODEL_NAME = "microsoft/xclip-base-patch16"

def l2norm(x: torch.Tensor) -> torch.Tensor:
    return x / (x.norm(p=2, dim=-1, keepdim=True) + 1e-12)

def main():
    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    print("device:", device)
    print("loading:", MODEL_NAME)

    processor = AutoProcessor.from_pretrained(MODEL_NAME)
    model = XCLIPModel.from_pretrained(MODEL_NAME).to(device)
    model.eval()

    query = "笑"
    inputs = processor(text=[query], return_tensors="pt", padding=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        out = model.get_text_features(
            input_ids=inputs["input_ids"],
            attention_mask=inputs.get("attention_mask", None),
            return_dict=True,
        )

    # out 可能是 Tensor，也可能是 BaseModelOutputWithPooling
    if isinstance(out, torch.Tensor):
        text_feat = out
    else:
        # 优先用 pooler_output
        if hasattr(out, "pooler_output") and out.pooler_output is not None:
            text_feat = out.pooler_output
        else:
            # 退化用 CLS token
            text_feat = out.last_hidden_state[:, 0, :]

    text_feat = l2norm(text_feat)[0].detach().cpu().numpy().astype(np.float32)


    print("query:", query)
    print("embedding shape:", text_feat.shape)
    print("embedding sample (first 8):", text_feat[:8])

if __name__ == "__main__":
    main()
