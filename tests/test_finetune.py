import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bls_rag import experiment
from bls_rag.evaluation.finetune_scoring import format_checks
from bls_rag.finetune_data import build, eval_gold_pages
from bls_rag.generation import ABSTENTION, RAG_SYSTEM
from bls_rag.paths import FINETUNE_DIR, RAG_EVAL_DIR


class FinetuneDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.examples = build(FINETUNE_DIR / 'train_questions.json', Path(cls.tmp.name) / 'train.jsonl', 3, 3500)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_size_and_mix_meet_assignment(self):
        self.assertTrue(20 <= len(self.examples) <= 50)
        self.assertGreaterEqual(sum(e['answerability'] == 'unanswerable' for e in self.examples), 5)

    def test_no_evaluation_gold_page_or_question_leaks_into_training(self):
        gold = {f'{f} p.{p}' for f, p in eval_gold_pages()}
        for example in self.examples:
            self.assertFalse(gold & set(example['context_pages']), example['id'])
        eval_questions = {q['question'] for q in json.loads((RAG_EVAL_DIR / 'questions.json').read_text())}
        self.assertFalse(eval_questions & {e['messages'][1]['content'] for e in self.examples})

    def test_prompt_is_the_inference_prompt(self):
        for example in self.examples:
            system = example['messages'][0]['content']
            self.assertTrue(system.startswith(RAG_SYSTEM.split('{context}')[0]))

    def test_targets_cite_real_passages_and_abstain_exactly(self):
        for example in self.examples:
            answer = example['messages'][2]['content']
            self.assertNotIn('{S:', answer)
            if example['answerability'] == 'unanswerable':
                self.assertEqual(answer, f'{ABSTENTION}\n\nSources: None')
                continue
            cites = {int(n) for n in re.findall(r'\[S(\d+)\]', answer)}
            self.assertTrue(cites and cites <= set(range(1, len(example['context_pages']) + 1)), example['id'])
            self.assertIn('\n\nSources: ', answer)

    def test_build_is_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            again = build(FINETUNE_DIR / 'train_questions.json', Path(d) / 'train.jsonl', 3, 3500)
        self.assertEqual(again, self.examples)


class FormatCheckTests(unittest.TestCase):
    def test_format_checks(self):
        good = format_checks('Rate was 4.5 percent [S2].\n\nSources: a.pdf (p. 3)', 4, True)
        self.assertTrue(good['has_citation'] and good['citations_in_range'] and good['has_sources_line'])
        self.assertFalse(format_checks('Rate [S7].', 4, True)['citations_in_range'])
        self.assertTrue(format_checks(ABSTENTION, 4, True)['exact_abstention'])
        self.assertNotIn('has_citation', format_checks('Closed book.', 0, False))


class ExperimentRunTests(unittest.TestCase):
    def test_run_records_every_arm_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            (directory / 'questions.json').write_text(json.dumps([{'id': 'Q1', 'question': 'q?'}]))
            (directory / 'experiment.json').write_text(json.dumps({'questions': 'questions.json', 'arms': [
                {'name': 'a', 'model': 'm1', 'retrieval': True}, {'name': 'b', 'model': 'm2', 'retrieval': False}]}))
            (directory / 'freeze_manifest.json').write_text('{}')
            settings = {'retrieval_mode': 'hybrid', 'top_k': 4, 'candidate_k': 16}

            class FakeLLM:
                last_call = {'elapsed_seconds': 0.1}

                def invoke(self, messages):
                    return SimpleNamespace(content='answer [S1]')

            with patch.object(experiment, 'validate', return_value={'settings': settings}), \
                 patch.object(experiment.index, 'load_chroma'), \
                 patch.object(experiment.retrieval, 'retrieve',
                              return_value=[{'rank': 1, 'source': 'x.pdf', 'page': 1, 'content': 'c'}]), \
                 patch.object(experiment.generation, 'get_llm', return_value=FakeLLM()):
                out = experiment.run(directory)
                row = json.loads(out.read_text())
                self.assertEqual(set(row['arms']), {'a', 'b'})
                self.assertEqual(row['arms']['a']['model'], 'm1')
                with self.assertRaises(SystemExit):
                    experiment.run(directory)
