"""QLoRA supervised fine-tuning. GPU execution is intentionally separate from CPU app setup."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import yaml
from evidencedoc.dataset import audit, records
from evidencedoc.prompt import system_prompt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path,default=Path("configs/qlora.yaml"))
    parser.add_argument("--dry-run",action="store_true")
    parser.add_argument("--max-steps",type=int,default=-1)
    args=parser.parse_args()
    cfg=yaml.safe_load(args.config.read_text())
    checked=audit(cfg["manifest"])
    rows=records(cfg["manifest"])
    if not checked["splits"].get("train") or not checked["splits"].get("validation"):
        raise ValueError("Both training and validation examples are required")
    if args.dry_run:
        print(json.dumps({"audit":checked,"model":cfg["model"],"config":cfg,"status":"data/config validated; no model loaded or trained"},indent=2));return
    import torch
    from datasets import Dataset
    from PIL import Image
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import SFTConfig, SFTTrainer
    if not torch.cuda.is_available():
        raise RuntimeError("Training requires an NVIDIA CUDA GPU; run --dry-run on your laptop")
    dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    processor=AutoProcessor.from_pretrained(cfg["model"],max_pixels=cfg["max_pixels"])
    quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type="nf4",bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=dtype) if cfg["quantize"] else None
    model=Qwen3VLForConditionalGeneration.from_pretrained(cfg["model"],quantization_config=quant,torch_dtype=dtype,device_map={"":0},attn_implementation="sdpa")
    model.config.use_cache=False
    if cfg["quantize"]:
        model=prepare_model_for_kbit_training(model)
    # Match language-model projections only: visual encoder stays frozen.
    targets=[name for name,_ in model.named_modules() if "visual" not in name and name.rsplit(".",1)[-1] in {"q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"}]
    if not targets:
        raise RuntimeError("No language projection modules found; inspect the model architecture")
    model=get_peft_model(model,LoraConfig(r=cfg["lora_rank"],lora_alpha=cfg["lora_alpha"],lora_dropout=.05,target_modules=targets,task_type="CAUSAL_LM",bias="none"))
    model.print_trainable_parameters()

    def example(row):
        image=Image.open(row["image_path"]).convert("RGB")
        label=json.loads(Path(row["label_path"]).read_text())
        return {"images":[image],"messages":[{"role":"system","content":system_prompt()},{"role":"user","content":[{"type":"text","text":"Parse these 1 page images in order."},{"type":"image"}]},{"role":"assistant","content":json.dumps(label,separators=(",",":"))}]}

    train=Dataset.from_list([example(r) for r in rows if r["split"]=="train"])
    validation=Dataset.from_list([example(r) for r in rows if r["split"]=="validation"])
    training=SFTConfig(output_dir=cfg["output_dir"],num_train_epochs=cfg["epochs"],max_steps=args.max_steps,per_device_train_batch_size=cfg["batch_size"],per_device_eval_batch_size=1,gradient_accumulation_steps=cfg["gradient_accumulation_steps"],learning_rate=cfg["learning_rate"],bf16=dtype==torch.bfloat16,fp16=dtype==torch.float16,gradient_checkpointing=True,gradient_checkpointing_kwargs={"use_reentrant":False},max_length=None,packing=False,assistant_only_loss=True,logging_steps=cfg["logging_steps"],save_steps=cfg["save_steps"],eval_strategy="epoch",report_to="none",seed=cfg["seed"],remove_unused_columns=False)
    trainer=SFTTrainer(model=model,args=training,processing_class=processor,train_dataset=train,eval_dataset=validation)
    torch.cuda.reset_peak_memory_stats()
    result=trainer.train()
    trainer.save_model(cfg["output_dir"])
    processor.save_pretrained(cfg["output_dir"])
    versions={p:importlib.metadata.version(p) for p in ["torch","transformers","trl","peft","datasets"]}
    meta={"config":cfg,"audit":checked,"versions":versions,"metrics":result.metrics,"gpu":torch.cuda.get_device_name(),"peak_allocated_gpu_bytes":torch.cuda.max_memory_allocated(),"training_completed":True}
    Path(cfg["output_dir"],"run_metadata.json").write_text(json.dumps(meta,indent=2))
    print(json.dumps(meta,indent=2))


if __name__=="__main__":main()
