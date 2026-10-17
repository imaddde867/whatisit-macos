# Minimal PEFT->GGUF LoRA writer (Qwen2, no q/k permutation). Mirrors convert_lora_to_gguf.py naming.
import sys,re,numpy as np,gguf
from safetensors.numpy import load_file
ad=load_file(sys.argv[1]); out=sys.argv[2]
m={'q_proj':'attn_q','k_proj':'attn_k','v_proj':'attn_v','o_proj':'attn_output','gate_proj':'ffn_gate','up_proj':'ffn_up','down_proj':'ffn_down'}
w=gguf.GGUFWriter(out,'qwen2')
w.add_type(gguf.GGUFType.ADAPTER); w.add_string(gguf.Keys.Adapter.TYPE,'lora'); w.add_float32(gguf.Keys.Adapter.LORA_ALPHA,160.0)
n=0
for k in sorted(ad):
    if 'lora_A' not in k: continue
    L=int(re.search(r'layers\.(\d+)\.',k).group(1)); mod=re.search(r'\.(\w+_proj)\.',k).group(1)
    base=f'blk.{L}.{m[mod]}.weight'
    w.add_tensor(base+'.lora_a',ad[k].astype(np.float32)); w.add_tensor(base+'.lora_b',ad[k.replace('lora_A','lora_B')].astype(np.float32)); n+=1
w.write_header_to_file(); w.write_kv_data_to_file(); w.write_tensors_to_file(); w.close(); print('pairs',n)
