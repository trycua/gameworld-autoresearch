"""Local tiny-architecture training tests; no pretrained 2B or Modal execution."""

from pathlib import Path
import tempfile
import unittest

import torch
from PIL import Image
from transformers import Qwen3VLConfig, Qwen3VLForConditionalGeneration

from fps_bench.qwen_lora import action_batch, train_and_reload, verify_adapter


def tiny_base():
    torch.manual_seed(5)
    config = Qwen3VLConfig(
        text_config={"vocab_size": 256, "hidden_size": 64, "intermediate_size": 128,
                     "num_hidden_layers": 2, "num_attention_heads": 4, "num_key_value_heads": 2,
                     "head_dim": 16, "rope_scaling": {"rope_type": "default", "mrope_section": [2, 3, 3]}},
        vision_config={"depth": 2, "hidden_size": 32, "intermediate_size": 64, "num_heads": 4,
                       "patch_size": 16, "temporal_patch_size": 2, "spatial_merge_size": 2,
                       "out_hidden_size": 64, "deepstack_visual_indexes": [0, 1]},
        image_token_id=200, video_token_id=201, vision_start_token_id=198, vision_end_token_id=199)
    return Qwen3VLForConditionalGeneration(config)


def tiny_batch():
    generator = torch.Generator().manual_seed(7)
    tokens = torch.tensor([[1, 198, 200, 199, 5, 6, 2]])
    labels = tokens.clone()
    labels[:, :4] = -100
    return {"input_ids": tokens, "attention_mask": torch.ones_like(tokens), "labels": labels,
            "pixel_values": torch.randn(4, 1536, generator=generator), "image_grid_thw": torch.tensor([[1, 2, 2]])}


class FakeProcessor:
    image_token_id = 200
    bad_prefix = False

    def apply_chat_template(self, messages, **kwargs):
        return "prompt" if kwargs["add_generation_prompt"] else "full"

    def __call__(self, text, **kwargs):
        result = tiny_batch()
        result.pop("labels")
        if text == ["prompt"]:
            result["input_ids"] = result["input_ids"][:, :4].clone()
            if self.bad_prefix:
                result["input_ids"][0, 0] = 8
            result["attention_mask"] = result["attention_mask"][:, :4]
        return result


class LoRATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.provenance = {"base_model": "tiny-random-qwen3-vl-test", "base_revision": "local-fixture",
                           "dataset_hash": "a" * 64, "contract_hash": "b" * 64}

    def test_real_image_update_saves_and_reloads_without_base_changes(self):
        base = tiny_base()
        frozen = {name: value.detach().clone() for name, value in base.named_parameters()}
        class Recorder:
            rows = []
            def record(self, *args, **kwargs):
                self.rows.append((args, kwargs))
        recorder = Recorder()
        result = train_and_reload(base, tiny_base, [tiny_batch()], self.home / "run", steps=2,
                                  telemetry=recorder, experiment="test", **self.provenance)
        self.assertEqual(len(recorder.rows), 2)
        self.assertEqual(recorder.rows[1][1]["step"], 2)
        self.assertEqual(recorder.rows[1][0][3]["gameworld_train_loss"], result["losses"][1]["loss"])
        self.assertEqual(result["telemetry_errors"], [])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["objective"], "sft")
        self.assertEqual(result["dataset_sha256"], "a" * 64)
        self.assertEqual(result["contract_sha256"], "b" * 64)
        self.assertEqual(result["steps"], 2)
        self.assertGreater(result["updated_parameter_tensors"], 0)
        self.assertLessEqual(result["reload_max_logit_error"], 1e-4)
        self.assertEqual(result["losses"][0]["supervised_tokens"], 3)
        current = dict(base.named_parameters())
        for name, initial in frozen.items():
            adapted_name = name.replace(".q_proj.weight", ".q_proj.base_layer.weight").replace(".v_proj.weight", ".v_proj.base_layer.weight")
            self.assertTrue(torch.equal(initial, current[adapted_name]), name)
        adapter = self.home / "run" / "adapter"
        verified = verify_adapter(adapter, result["adapter_manifest_sha256"], "tiny-random-qwen3-vl-test",
                                  "local-fixture", "a" * 64, "b" * 64)
        self.assertEqual(verified["objective"], "sft")
        self.assertEqual(verified["hyperparameters"]["rank"], 8)
        weights = adapter / "adapter_model.safetensors"
        weights.write_bytes(weights.read_bytes() + b"changed")
        with self.assertRaises(ValueError):
            verify_adapter(adapter, result["adapter_manifest_sha256"], "tiny-random-qwen3-vl-test",
                           "local-fixture", "a" * 64, "b" * 64)

    def test_telemetry_failure_does_not_discard_adapter(self):
        class BrokenRecorder:
            def record(self, *args, **kwargs):
                raise OSError("sensitive provider detail should not appear in artifacts")
        result = train_and_reload(tiny_base(), tiny_base, [tiny_batch()], self.home / "run",
                                  telemetry=BrokenRecorder(), experiment="failed-export", **self.provenance)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["telemetry_errors"], [{"step": 1, "error_type": "OSError"}])

    def test_bounds_fail_before_creating_output(self):
        for steps in (0, 33, True):
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                train_and_reload(tiny_base(), tiny_base, [tiny_batch()], self.home / "run", steps=steps, **self.provenance)
        batch = tiny_batch()
        batch.pop("pixel_values")
        with self.assertRaises(ValueError):
            train_and_reload(tiny_base(), tiny_base, [batch], self.home / "run", **self.provenance)
        self.assertFalse((self.home / "run").exists())

    def test_prompt_and_image_tokens_masked(self):
        Image.new("RGB", (32, 32)).save(self.home / "image.png")
        sample = {"messages": [{"role": "system", "content": "test"}, {"role": "user", "content": [
            {"type": "text", "text": "choose"}, {"type": "image", "image": "image.png"}]}],
            "completion": [{"role": "assistant", "content": '{"action":"key","key":"left"}'}]}
        batch = action_batch(FakeProcessor(), sample, self.home)
        self.assertEqual(batch["labels"].tolist(), [[-100, -100, -100, -100, 5, 6, 2]])
        processor = FakeProcessor()
        processor.bad_prefix = True
        with self.assertRaises(ValueError):
            action_batch(processor, sample, self.home)
        with self.assertRaises(ValueError):
            action_batch(FakeProcessor(), sample, self.home, max_tokens=4)


if __name__ == "__main__":
    unittest.main()
