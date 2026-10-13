#!/usr/bin/env python3
"""Train the verified chat labels on the original NL2SH GGUF, then export a merged GGUF.

Run only after the issue #9 human review and #17 full-run gates have passed.
No evaluation files are read. --steps 0 checks the CUDA conversion without training.
"""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import shutil
import time

from check_corpus import jaccard, words
from finetune_roundtrip import tensor_names, weight_digest, write_gguf
from whatisit_macos.local_recovery_worker import MACOS_PREFIX


def chat_tokens(row, tokenizer, system_prompt):
    messages = row.get('messages')
    if (not isinstance(messages, list) or len(messages) != 3 or
            any(not isinstance(m, dict) for m in messages) or
            [m.get('role') for m in messages] != ['system', 'user', 'assistant'] or
            any(not isinstance(m.get('content'), str) for m in messages) or
            messages[0]['content'] != system_prompt or
            not messages[1]['content'].startswith(MACOS_PREFIX)):
        raise ValueError('dataset record does not match serving chat format')
    target = messages[2]['content']
    if len(target) > 4096 or any(c in target for c in '\x00\r\n'):
        raise ValueError('invalid assistant target')
    prefix = tokenizer.apply_chat_template(messages[:2], tokenize=True, return_dict=False,
                                          add_generation_prompt=True)
    tokens = tokenizer.apply_chat_template(messages, tokenize=True, return_dict=False,
                                          add_generation_prompt=False)
    if tokens[:len(prefix)] != prefix or len(tokens) > 512:
        raise ValueError('chat prefix differs or sequence exceeds the measured 512-token budget')
    if tokenizer.convert_tokens_to_ids('<|im_end|>') not in tokens[len(prefix):]:
        raise ValueError('assistant target lacks its end-of-turn token')
    return tokens, [-100] * len(prefix) + tokens[len(prefix):]


def split_validation(rows, fraction):
    """Fixed split by command/empty kind, grouping source families, shared commands and near-duplicate requests."""
    rng = random.Random(0)
    if any(isinstance(row.get('source_id'), str) and row['source_id'] for row in rows):
        parent = list(range(len(rows)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        first = {}
        for i, row in enumerate(rows):
            source_id = row.get('source_id')
            command = row['messages'][2]['content']
            for link in (('source', source_id) if isinstance(source_id, str) and source_id else None,
                         ('command', command) if command else None):
                if link:
                    parent[find(i)] = find(first.setdefault(link, i))
        requests = [words(row['messages'][1]['content'].removeprefix(MACOS_PREFIX)) for row in rows]
        for i in range(len(rows)):  # ponytail: O(n^2) Jaccard, fine for a few thousand rows
            for j in range(i):
                if jaccard(requests[i], requests[j]) >= 0.7:
                    parent[find(i)] = find(j)
        groups = {}
        for i in range(len(rows)):
            groups.setdefault(rows[find(i)]['id'], []).append(i)
        strata = {}
        for key, indices in groups.items():
            empty = sum(rows[i]['messages'][2]['content'] == '' for i in indices)
            signature = (empty, len(indices) - empty)
            strata.setdefault(signature, []).append(key)
        val_groups = set()
        quotas = {signature: len(keys) * fraction for signature, keys in strata.items()}
        cuts = {signature: int(quota) for signature, quota in quotas.items()}
        remainder = round(len(groups) * fraction) - sum(cuts.values())
        for signature in sorted(strata, key=lambda s: quotas[s] - cuts[s], reverse=True)[:remainder]:
            cuts[signature] += 1
        for signature, keys in strata.items():
            rng.shuffle(keys)
            val_groups.update(keys[:cuts[signature]])
        val = [i for key in val_groups for i in groups[key]]
        return sorted(set(range(len(rows))) - set(val)), sorted(val)
    train, val = [], []
    for empty in (False, True):
        group = [i for i, r in enumerate(rows) if (r['messages'][2]['content'] == '') == empty]
        rng.shuffle(group)
        cut = round(len(group) * fraction)
        val += group[:cut]
        train += group[cut:]
    return sorted(train), sorted(val)


def main():
    run_started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('metadata', type=Path)
    parser.add_argument('data', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--steps', type=int, default=1000)
    parser.add_argument('--lr', type=float, default=1e-5)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--val-fraction', type=float, default=0.0,
                        help='share of rows (per kind) or, with source_id, of grouped families held out for validation loss; 0 trains on all rows')
    args = parser.parse_args()
    if args.steps < 0 or args.output.exists():
        parser.error('steps must be nonnegative and output must be a new directory')
    if not 0 <= args.val_fraction < 0.5 or args.lr <= 0:
        parser.error('val-fraction must be in [0, 0.5) and lr positive')

    import numpy as np
    import torch
    from gguf import GGUFReader, GGMLQuantizationType, dequantize
    from peft import LoraConfig, get_peft_model
    from transformers import AutoTokenizer, Qwen2Config, Qwen2ForCausalLM
    from whatisit import config

    if not torch.cuda.is_available():
        raise RuntimeError('CUDA GPU required')
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    rng = random.Random(args.seed)
    tokenizer = AutoTokenizer.from_pretrained(str(args.metadata), local_files_only=True)
    rows = [json.loads(line) for line in args.data.read_text().splitlines() if line.strip()]
    if not rows or len({row['id'] for row in rows}) != len(rows):
        raise ValueError('dataset must contain nonempty, unique records')
    encoded_all = [chat_tokens(row, tokenizer, config.SYSTEM_PROMPT) for row in rows]
    train_idx, val_idx = split_validation(rows, args.val_fraction)
    train_source_ids = sorted({rows[i].get('source_id') or rows[i]['id'] for i in train_idx})
    val_source_ids = sorted({rows[i].get('source_id') or rows[i]['id'] for i in val_idx})
    encoded = [encoded_all[i] for i in train_idx]
    validation = [encoded_all[i] for i in val_idx]
    reader = GGUFReader(str(args.source))
    if (reader.fields['general.architecture'].contents() != 'qwen2' or
            reader.fields['tokenizer.chat_template'].contents() != tokenizer.chat_template):
        raise ValueError('source architecture or chat template differs from serving')
    model_config = Qwen2Config.from_pretrained(str(args.metadata), local_files_only=True)
    model = Qwen2ForCausalLM(model_config)
    shapes = {name: tuple(value.shape) for name, value in model.named_parameters()}
    names = tensor_names(shapes, [t.name for t in reader.tensors], model_config.num_hidden_layers)
    by_name = {t.name: t for t in reader.tensors}
    weights, original = {}, {}
    for name, gguf_name in names.items():
        tensor = by_name[gguf_name]
        if shapes[name] != tuple(int(d) for d in tensor.shape[::-1]):
            raise ValueError(f'source shape mismatch: {name}')
        value = dequantize(tensor.data, tensor.tensor_type).reshape(shapes[name])
        if tensor.tensor_type != GGMLQuantizationType.F32:
            value = value.astype(np.float16)
        if not np.isfinite(value).all():
            raise ValueError(f'nonfinite source tensor: {name}')
        weights[name] = torch.from_numpy(value.copy())
        original[name] = weight_digest(value)
    if model_config.tie_word_embeddings:
        weights['lm_head.weight'] = weights['model.embed_tokens.weight']
    model.load_state_dict(weights, strict=True, assign=True)
    model.tie_weights()
    del weights, value
    modules = ['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj']
    model = get_peft_model(model, LoraConfig(r=8, lora_alpha=160, lora_dropout=0,
                          target_modules=modules,
                          layers_to_transform=list(range(model_config.num_hidden_layers - 16,
                                                         model_config.num_hidden_layers)),
                          task_type='CAUSAL_LM'))
    count = sum(p.numel() for p in model.parameters() if p.requires_grad)
    if count != 5275648:
        raise ValueError(f'LoRA differs from the feasibility configuration: {count} parameters')
    model.to('cuda')
    model.train()
    model.config.use_cache = False
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=args.lr)
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    losses, order, val_losses = [], [], []

    def validate(step):
        if not validation:
            return
        model.eval()
        with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
            total = sum(float(model(input_ids=torch.tensor([t], device='cuda'),
                                    labels=torch.tensor([l], device='cuda')).loss) for t, l in validation)
        model.train()
        val_losses.append([step, total / len(validation)])
        print(f'step {step}: validation loss={val_losses[-1][1]:.4f} ({len(validation)} rows)', flush=True)

    validate(0)
    for step in range(args.steps):
        if not order:
            order = list(range(len(encoded)))
            rng.shuffle(order)
        tokens, labels = encoded[order.pop()]
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast('cuda', dtype=torch.bfloat16):
            loss = model(input_ids=torch.tensor([tokens], device='cuda'),
                         labels=torch.tensor([labels], device='cuda')).loss
        if not torch.isfinite(loss):
            raise RuntimeError(f'nonfinite loss at step {step + 1}')
        loss.backward()
        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
        optimizer.step()
        losses.append(float(loss.detach()))
        if (step + 1) % 50 == 0:
            print(f'step {step + 1}/{args.steps}: loss={losses[-1]:.4f}, grad={float(grad_norm):.4f}', flush=True)
        if (step + 1) % 100 == 0:
            validate(step + 1)
    if args.steps % 100:
        validate(args.steps)
    torch.cuda.synchronize()
    wall = time.monotonic() - started
    peak = torch.cuda.max_memory_allocated()
    merged = model.merge_and_unload(safe_merge=True).cpu()
    parameters = {name: value.detach().numpy() for name, value in merged.named_parameters()}
    if args.steps == 0 and original != {n: weight_digest(v) for n, v in parameters.items()}:
        raise ValueError('zero-update CUDA import/merge changed source weights')
    args.output.mkdir(parents=True)
    merged.save_pretrained(args.output / 'fused')
    tokenizer.save_pretrained(args.output / 'fused')
    for filename in ('LICENSE',):
        shutil.copy2(args.metadata / filename, args.output / filename)
    shutil.copy2(Path(__file__).resolve().parents[1] / 'docs/finetune-NOTICE.txt', args.output / 'NOTICE')
    write_gguf(reader, parameters, args.output / 'merged-f16.gguf', model_config.num_hidden_layers)
    report = {'steps': args.steps, 'seed': args.seed, 'batch_size': 1, 'sequence_limit': 512,
              'learning_rate': args.lr, 'optimizer': 'AdamW', 'autocast': 'bfloat16', 'lora_rank': 8,
              'lora_alpha': 160, 'lora_scale': 20, 'lora_layers': 16,
              'val_fraction': args.val_fraction, 'train_rows': len(train_idx), 'val_ids': [rows[i]['id'] for i in val_idx],
              'val_source_ids': val_source_ids,
              'source_group_counts': {'train': len(train_source_ids), 'validation': len(val_source_ids)},
              'validation_losses': val_losses, 'trainable_parameters': count, 'data_sha256': hashlib.sha256(args.data.read_bytes()).hexdigest(),
              'source_sha256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
              'gpu': torch.cuda.get_device_name(), 'cuda': torch.version.cuda,
              'wall_seconds': time.monotonic() - run_started, 'training_wall_seconds': wall,
              'training_peak_allocated_bytes': peak, 'losses': losses,
              'zero_update_weights_equal': True if args.steps == 0 else None,
              'packages': {p: importlib.metadata.version(p) for p in ('torch', 'transformers', 'peft', 'gguf')}}
    (args.output / 'training-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'losses'}), flush=True)


if __name__ == '__main__':
    main()
