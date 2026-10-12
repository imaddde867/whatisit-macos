"""Local zero-update NL2SH GGUF feasibility experiment (issue #8).

Run `roundtrip SOURCE METADATA OUTPUT`, then `probe OUTPUT/dequantized`
and `prompt OUTPUT/fused` with PYTHONPATH=src and WHATISIT_MODEL set.
Artifacts must be outside the repo. No eval data is loaded here.
"""

import argparse
import hashlib
import json
from pathlib import Path
import resource
import shutil

LORA = {'rank': 8, 'scale': 20.0, 'dropout': 0.0}
LAYERS = 16


def weight_digest(array):
    array = array.copy()
    array[array == 0] = 0  # Zero-adapter addition can change -0.0 to +0.0.
    return hashlib.sha256(str((array.dtype, array.shape)).encode() + array.tobytes()).hexdigest()


def tensor_names(parameters, source_names, num_layers):
    from gguf import MODEL_ARCH, get_tensor_name_map

    mapping = get_tensor_name_map(MODEL_ARCH.QWEN2, num_layers)
    names = {p: mapping.get_name(p, try_suffixes=('.weight', '.bias')) for p in parameters}
    if None in names.values() or len(set(names.values())) != len(names):
        raise ValueError('Unknown or duplicate Qwen2 tensor mapping')
    if set(names.values()) != set(source_names):
        raise ValueError('GGUF tensors do not exactly match the model parameters')
    return names


def write_gguf(reader, parameters, output, num_layers):
    """Keep source metadata and exact tensor coverage when exporting merged weights."""
    import numpy as np
    from gguf import GGUFWriter, GGUFValueType

    names = tensor_names(parameters, [t.name for t in reader.tensors], num_layers)
    source = {t.name: t for t in reader.tensors}
    for name, value in parameters.items():
        if value.shape != tuple(int(d) for d in source[names[name]].shape[::-1]):
            raise ValueError(f'Shape mismatch for {name}')
        if not np.isfinite(value).all():
            raise ValueError(f'Non-finite exported tensor {name}')
    writer = GGUFWriter(output, 'qwen2', use_temp_file=True)
    for key, field in reader.fields.items():
        if key.startswith('GGUF.') or key in ('general.architecture', 'general.file_type'):
            continue
        writer.add_key_value(key, field.contents(), field.types[0],
                             field.types[1] if field.types[0] == GGUFValueType.ARRAY else None)
    writer.add_file_type(1)
    for name, value in parameters.items():
        writer.add_tensor(names[name], value)
    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file(progress=True)
    writer.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('roundtrip', 'probe', 'prompt'))
    parser.add_argument('source', type=Path)
    parser.add_argument('metadata', nargs='?', type=Path)
    parser.add_argument('output', nargs='?', type=Path)
    args = parser.parse_args()

    import mlx.core as mx
    import mlx.nn as nn
    import numpy as np
    from mlx.utils import tree_flatten, tree_unflatten
    from mlx_lm.tuner.utils import linear_to_lora_layers

    mx.random.seed(42)
    if args.action == 'prompt':
        import subprocess
        from unittest.mock import patch
        from gguf import GGUFReader
        from mlx_lm.tuner.datasets import ChatDataset
        from transformers import AutoTokenizer
        from whatisit import config, engine
        from whatisit_macos import local_recovery_worker

        tokenizer = AutoTokenizer.from_pretrained(str(args.source), local_files_only=True)
        reader = GGUFReader(str(config.find_model()))
        assert tokenizer.chat_template == reader.fields['tokenizer.chat_template'].contents()
        prefix = local_recovery_worker.MACOS_PREFIX
        cases = [json.loads(line) for line in
                 (Path(__file__).resolve().parents[1] / 'eval/dev.jsonl').read_text().splitlines()]
        cases.append({'id': 'explicit-unicode-input', 'request': 'inspect this folder',
                      'path': '/tmp/é space'})
        audited = {}
        for case in cases:
            payload = {'request': case['request'], 'path': case.get('path')}
            # Capture the real serving HTTP body; inference is unnecessary for formatting.
            with patch.object(engine, '_post', return_value=[('pwd', 'stop')]) as post:
                answer = local_recovery_worker.suggest(payload, harness='model')
            assert post.called, answer['reason']
            serving = post.call_args.args[1]['messages']
            user = prefix + case['request']
            if payload['path'] is not None:
                user += '\nExplicit inputs: ' + json.dumps({'path': payload['path']}, ensure_ascii=False)
            training = [{'role': 'system', 'content': config.SYSTEM_PROMPT},
                        {'role': 'user', 'content': user}]
            assert training == serving, case['id']
            rendered = tokenizer.apply_chat_template(training, tokenize=False, add_generation_prompt=True)
            actual = engine._request('/apply-template', {'messages': serving})['prompt']
            assert rendered.encode() == actual.encode(), case['id']
            token_ids = tokenizer.encode(actual, add_special_tokens=False)
            served_tokens = engine._request('/tokenize', {'content': actual, 'add_special': False})['tokens']
            assert token_ids == served_tokens, case['id']
            item = {'messages': training + [{'role': 'assistant', 'content': 'pwd'}]}
            tokens, offset = ChatDataset([item], tokenizer, mask_prompt=True).process(item)
            assert tokens[:offset] == token_ids, case['id']
            empty = {'messages': training + [{'role': 'assistant', 'content': ''}]}
            empty_tokens, empty_offset = ChatDataset([empty], tokenizer, mask_prompt=True).process(empty)
            assert empty_tokens[:empty_offset] == token_ids, case['id']
            assert tokenizer.convert_tokens_to_ids('<|im_end|>') in empty_tokens[empty_offset:], case['id']
            audited[case['id']] = hashlib.sha256(actual.encode()).hexdigest()
        report = {'cases': len(audited), 'bytes_and_tokens_equal': True,
                  'empty_target_includes_end_of_turn': True,
                  'system_prompt': config.SYSTEM_PROMPT, 'user_prefix': prefix,
                  'prompt_hashes': audited,
                  'server': subprocess.check_output(['pgrep', '-fl', 'llama-server'], text=True).strip()}
        (args.source.parent / 'prompt-audit.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({k: v for k, v in report.items() if k != 'prompt_hashes'}), flush=True)
        return

    if args.action == 'probe':
        from mlx_lm import load
        import mlx.optimizers as optim
        from mlx_lm.tuner.trainer import default_loss

        model, _ = load(str(args.source))
        model.freeze()
        linear_to_lora_layers(model, LAYERS, LORA)
        model.train()
        optimizer = optim.AdamW(learning_rate=1e-5)
        optimizer.init(model.trainable_parameters())
        mx.eval(model.parameters(), optimizer.state)
        mx.clear_cache()
        mx.reset_peak_memory()
        # Synthetic token IDs exercise full-length backward without training/eval data.
        batch = mx.arange(513, dtype=mx.int32)[None, :]
        loss_and_grad = nn.value_and_grad(model, default_loss)
        (loss, tokens), grads = loss_and_grad(model, batch, mx.array([[0, 512]]))
        mx.eval(loss, tokens, grads, optimizer.state)
        assert bool(mx.isfinite(loss)), 'Non-finite backward loss'
        assert all(bool(mx.all(mx.isfinite(g))) for _, g in tree_flatten(grads))
        assert any(bool(mx.any(g != 0)) for _, g in tree_flatten(grads))
        report = {'batch_size': 1, 'sequence_length': 512, 'lora_layers': LAYERS,
                  'lora': LORA, 'seed': 42, 'optimizer': 'AdamW', 'updates': 0,
                  'loss': float(loss), 'mlx_peak_bytes': mx.get_peak_memory(),
                  'max_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  'trainable_parameters': sum(p.size for _, p in tree_flatten(model.trainable_parameters()))}
        (args.source.parent / 'memory-probe.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report), flush=True)
        return

    if args.metadata is None or args.output is None:
        parser.error('roundtrip requires SOURCE METADATA OUTPUT')
    from gguf import GGUFReader, GGMLQuantizationType, dequantize
    from mlx_lm.models.qwen2 import Model, ModelArgs

    reader = GGUFReader(str(args.source))
    if reader.fields['general.architecture'].contents() != 'qwen2':
        raise ValueError('Only the default Qwen2 architecture is supported')
    config = json.loads((args.metadata / 'config.json').read_text())
    model = Model(ModelArgs.from_dict(config))
    shapes = {p: v.shape for p, v in tree_flatten(model.parameters())}
    names = tensor_names(shapes, [t.name for t in reader.tensors], config['num_hidden_layers'])
    by_name = {t.name: t for t in reader.tensors}
    for p, n in names.items():
        if shapes[p] != tuple(int(d) for d in by_name[n].shape[::-1]):
            raise ValueError(f'Shape mismatch for {p}')
    args.output.mkdir(parents=True, exist_ok=False)
    notice = Path(__file__).resolve().parents[1] / 'docs/finetune-NOTICE.txt'
    shutil.copy2(notice, args.output / 'NOTICE')
    shutil.copy2(args.metadata / 'LICENSE', args.output / 'LICENSE')
    dequantized = args.output / 'dequantized'
    shutil.copytree(args.metadata, dequantized, ignore=shutil.ignore_patterns('.cache'))
    shutil.copy2(notice, dequantized / 'NOTICE')
    weights = []
    for p, n in names.items():
        t = by_name[n]
        array = dequantize(t.data, t.tensor_type).reshape(shapes[p])
        if t.tensor_type != GGMLQuantizationType.F32:
            array = array.astype(np.float16)
        if not np.isfinite(array).all():
            raise ValueError(f'Non-finite source tensor {n}')
        weights.append((p, mx.array(array)))
    model.load_weights(weights, strict=True)
    del weights, array
    mx.eval(model.parameters())
    mx.save_safetensors(str(dequantized / 'model.safetensors'), dict(tree_flatten(model.parameters())))
    before = {p: weight_digest(np.asarray(v))
              for p, v in tree_flatten(model.parameters())}
    print(f'Imported {len(names)} tensors; attaching zero-initialized LoRA', flush=True)

    model.freeze()
    linear_to_lora_layers(model, LAYERS, LORA)
    mx.eval(model.trainable_parameters())
    assert all(bool(mx.all(v == 0)) for p, v in tree_flatten(model.trainable_parameters())
               if p.endswith('lora_b'))
    for layer in model.layers[-LAYERS:]:
        fused = [(n, m.fuse()) for n, m in layer.named_modules() if hasattr(m, 'fuse')]
        layer.update_modules(tree_unflatten(fused))
        mx.eval(layer.parameters())
        del fused
        mx.clear_cache()
    after = {p: weight_digest(np.asarray(v))
             for p, v in tree_flatten(model.parameters())}
    assert before == after, 'No-op adapter changed model weights'
    fused_path = args.output / 'fused'
    shutil.copytree(args.metadata, fused_path, ignore=shutil.ignore_patterns('.cache'))
    shutil.copy2(notice, fused_path / 'NOTICE')
    mx.save_safetensors(str(fused_path / 'model.safetensors'), dict(tree_flatten(model.parameters())))

    parameters = dict(tree_flatten(model.parameters()))
    write_gguf(reader, {p: np.asarray(v) for p, v in parameters.items()},
               args.output / 'roundtrip-f16.gguf', config['num_hidden_layers'])
    (args.output / 'roundtrip.json').write_text(json.dumps(
        {'source': str(args.source.resolve()), 'tensors': len(names),
         'no_op_weights_equal_except_zero_sign': True,
         'lora_layers': LAYERS, 'lora': LORA, 'seed': 42, 'updates': 0}, indent=2) + '\n')
    print('No-op merge preserved every tensor; exported roundtrip-f16.gguf', flush=True)


if __name__ == '__main__':
    main()
