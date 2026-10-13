"""Merge a trained LoRA adapter into unquantized base weights for serving."""
import argparse


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("adapter")
    parser.add_argument("--output",default="checkpoints/evidencedoc-merged")
    args=parser.parse_args()
    import torch
    from peft import PeftConfig,PeftModel
    from transformers import AutoProcessor,Qwen3VLForConditionalGeneration
    config=PeftConfig.from_pretrained(args.adapter)
    dtype=torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float32
    base=Qwen3VLForConditionalGeneration.from_pretrained(config.base_model_name_or_path,torch_dtype=dtype,device_map="auto")
    merged=PeftModel.from_pretrained(base,args.adapter).merge_and_unload(safe_merge=True)
    merged.save_pretrained(args.output,safe_serialization=True)
    AutoProcessor.from_pretrained(args.adapter).save_pretrained(args.output)
    print("Merged model saved:",args.output)


if __name__=="__main__":main()
