"""Conversion boundary checks; run with the feasibility environment's Python."""

import unittest

from finetune_roundtrip import tensor_names, weight_digest


class TensorNamesTests(unittest.TestCase):
    def test_noop_comparison_ignores_signed_zero_but_catches_changed_weights(self):
        import numpy as np

        a = np.array([-0.0, 1.0], dtype=np.float16)
        self.assertEqual(weight_digest(a), weight_digest(np.array([0.0, 1.0], dtype=np.float16)))
        self.assertNotEqual(weight_digest(a), weight_digest(np.array([0.0, 1.01], dtype=np.float16)))
        self.assertNotEqual(weight_digest(a), weight_digest(a.astype(np.float32)))
        self.assertNotEqual(weight_digest(a), weight_digest(a.reshape(1, 2)))

    def test_qwen_mapping_keeps_biases_and_tied_embeddings(self):
        names = ['model.embed_tokens.weight', 'model.norm.weight',
                 'model.layers.0.self_attn.q_proj.weight',
                 'model.layers.0.self_attn.k_proj.bias',
                 'model.layers.0.mlp.down_proj.weight']
        source = ['token_embd.weight', 'output_norm.weight',
                  'blk.0.attn_q.weight', 'blk.0.attn_k.bias', 'blk.0.ffn_down.weight']
        self.assertEqual(tensor_names(names, source, 1), dict(zip(names, source)))

    def test_unmapped_or_extra_tensor_fails_instead_of_random_weights(self):
        for names, source in [(['model.unknown.weight'], ['token_embd.weight']),
                              (['model.norm.weight'], []),
                              (['model.norm.weight'], ['output_norm.weight', 'output.weight'])]:
            with self.subTest(names=names, source=source), self.assertRaises(ValueError):
                tensor_names(names, source, 1)


if __name__ == '__main__':
    unittest.main()
