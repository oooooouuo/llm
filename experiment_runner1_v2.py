"""Multilingual WSD runner. See docs/reproduce.md for evaluation boundaries."""
from __future__ import annotations
import argparse
from pathlib import Path
from preflight import validate_inputs
from evaluation import gold_ids

import os
import time
import re
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict, field
import sys
from uuid import uuid4
BABELNET_CACHE_FILE = 'resources/babelnet_inventory_cache_healed.json'
PROGRESS_CACHE_FILE = 'experiment_progress.json'
TEMP_RESULT_DIR = 'temp_experiment_results'
EXPERIMENT_CONFIG = {'cross_lingual_model': os.environ.get('WSD_E5_MODEL', 'intfloat/multilingual-e5-large'), 'semantic_sampler_model': os.environ.get('WSD_SAMPLER_MODEL', 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'), 'sampler_alpha': 2.0, 'e5_retrieve_k': 15, 'complexity_weights': {'word': 1.0, 'punct': 0.2}, 'random_seed': 42, 'request_interval': 1.2, 'save_prompt': False, 'save_response': False, 'debug_mode': False, 'debug_sample_size': 30, 'real_data_config': {'e5_similarity_threshold': 0.82, 'bridge_pre_k': 2, 'sampler_alpha': 1.0, 'fallback_only_when_empty': True}}

@dataclass
class ExperimentResult:
    experiment_id: str
    model_name: str
    data_source: str
    target_language: str
    data_level: str
    system_version: str
    accuracy: float = 0.0
    improvement: Optional[float] = None
    total_samples: int = 0
    correct_samples: int = 0
    run_timestamp: str = ''
    sampler_alpha: float = 2.0
    complexity_strategy: str = ''
    fallback_count: int = 0
    avg_complexity_score: float = 0.0

@dataclass
class SampleLevelResult:
    sample_id: str
    experiment_id: str
    model_name: str
    data_source: str
    target_language: str
    data_level: str
    system_version: str
    target_word: str
    original_sentence: str
    clean_sentence: str
    ground_truth_senseid: str
    candidate_senses: List[Dict]
    complexity_score: float
    adaptive_k: int
    use_cot: bool
    level_judged: str
    cross_lingual_retrieve_success: bool
    retrieve_example_count: int
    prompt: Optional[str]
    model_response: Optional[str]
    is_correct: bool
    sample_run_timestamp: str
    request_metadata: Dict = field(default_factory=dict)

def extract_target_word(sentence: str) -> str:
    if not isinstance(sentence, str):
        return ''
    match = re.search('<WSD>(.*?)</?WSD>', sentence, re.IGNORECASE)
    return match.group(1).strip() if match else ''

def clean_sentence(sentence: str) -> str:
    return re.sub('</?WSD>', '', sentence, flags=re.IGNORECASE).strip()

class ActualComplexityAnalyzer:

    def __init__(self):
        self.w_word = EXPERIMENT_CONFIG['complexity_weights']['word']
        self.w_punct = EXPERIMENT_CONFIG['complexity_weights']['punct']

    def calculate_complexity(self, sentence: str) -> float:
        words = sentence.split()
        word_count = len(words)
        punct_count = len(re.findall('[.,!?;:()"-]', sentence))
        return self.w_word * word_count + self.w_punct * punct_count

    def get_adaptive_strategy(self, sentence: str) -> Dict:
        score = self.calculate_complexity(sentence)
        if score < 15.0:
            return {'k': 3, 'use_cot': False, 'level_judged': 'simple', 'score': score}
        elif score < 30.0:
            return {'k': 5, 'use_cot': False, 'level_judged': 'medium', 'score': score}
        else:
            return {'k': 5, 'use_cot': True, 'level_judged': 'complex', 'score': score}

class CrossLingualE5Retriever:

    def __init__(self):
        self.model = SentenceTransformer(EXPERIMENT_CONFIG['cross_lingual_model'])
        self._embedding_cache = {}

    def encode(self, sentences: List[str], lang: str) -> np.ndarray:
        prefix = {'en': 'en', 'fr': 'fr', 'de': 'de', 'es': 'es', 'it': 'it'}.get(lang, 'en')
        formatted = [f'{prefix}: {s}' for s in sentences]
        missing = list(dict.fromkeys(x for x in formatted if x not in self._embedding_cache))
        if missing:
            vectors = self.model.encode(missing, normalize_embeddings=True, show_progress_bar=False)
            self._embedding_cache.update(zip(missing, vectors))
        return np.asarray([self._embedding_cache[x] for x in formatted])

    def retrieve(self, target_sent: str, target_lang: str, english_pool: List[Dict], pre_k: int=15) -> List[Dict]:
        if not english_pool:
            return []
        src_sentences = [clean_sentence(x.get('sentence', '')) for x in english_pool]
        tgt_emb = self.encode([clean_sentence(target_sent)], target_lang)
        src_emb = self.encode(src_sentences, 'en')
        sims = np.dot(src_emb, tgt_emb.T).flatten()
        top_idx = np.argsort(sims)[-pre_k:][::-1]
        return [english_pool[int(i)] for i in top_idx]

class DynamicSemanticSampler:

    def __init__(self, alpha: float=2.0):
        self.alpha = alpha
        self.model = SentenceTransformer(EXPERIMENT_CONFIG['semantic_sampler_model'])

    def sample(self, target_sentence: str, candidate_examples: List[Dict], k: int) -> List[Dict]:
        if not candidate_examples:
            return []
        if len(candidate_examples) <= k:
            return candidate_examples
        examples_text = [clean_sentence(ex.get('sentence', '')) for ex in candidate_examples]
        target_emb = self.model.encode([clean_sentence(target_sentence)], normalize_embeddings=True, show_progress_bar=False)
        ex_embs = self.model.encode(examples_text, normalize_embeddings=True, show_progress_bar=False)
        sims = np.clip(np.dot(ex_embs, target_emb.T).flatten(), 0.0, 1.0)
        if len(sims) > 1:
            sims = (sims - sims.min()) / (sims.max() - sims.min() + 1e-08)
        weights = [ex.get('frequency_weight', 1.0) * (1.0 + self.alpha * s) for ex, s in zip(candidate_examples, sims)]
        top_k_indices = np.argsort(np.array(weights))[-k:][::-1]
        return [candidate_examples[i] for i in top_k_indices]

class ActualFusionRunner:

    def __init__(self, data_dir, support_dir, output_dir, data_type, models, languages, versions, levels):
        self.data_dir = str(data_dir)
        self.support_dir = str(support_dir)
        self.versions = versions
        self.levels = levels
        self.data_types = data_type
        self.allow_missing_english = False
        if EXPERIMENT_CONFIG.get('debug_mode', False):
            self.output_dir = output_dir
            self.temp_result_dir = os.path.join(output_dir, 'debug_' + TEMP_RESULT_DIR)
            self.progress_file = os.path.join(output_dir, 'debug_' + PROGRESS_CACHE_FILE)
            print('🚀 [注意] 当前处于沙盒测试模式 (DEBUG MODE)，仅小量测试，不会覆盖原文件！')
        else:
            self.output_dir = output_dir
            self.temp_result_dir = os.path.join(output_dir, TEMP_RESULT_DIR)
            self.progress_file = os.path.join(output_dir, PROGRESS_CACHE_FILE)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_result_dir, exist_ok=True)
        self.models = models
        self.target_langs = languages
        self.cl_retriever = CrossLingualE5Retriever()
        self.sampler = DynamicSemanticSampler(alpha=EXPERIMENT_CONFIG['sampler_alpha'])
        self.real_sampler = None
        self.analyzer = ActualComplexityAnalyzer()
        self.inventory = self._load_babelnet_cache()
        self.model_interfaces = {}
        for model_name in self.models:
            try:
                self.model_interfaces[model_name] = UnifiedModelInterface(model_name=model_name)
                print(f'✅ 初始化 {model_name} 接口成功')
            except Exception as e:
                raise RuntimeError(f'初始化 {model_name} 接口失败') from e
        self.run_ts = time.strftime('%Y%m%d_%H%M%S') + '_' + uuid4().hex[:8]
        self.completed_tasks = []
        self.existing_summary = []
        self.existing_samples = []
        self.sense_to_en_lemmas = {}
        for key, senses in self.inventory.items():
            if key.startswith('en:'):
                lemma = key.split(':', 1)[1].lower()
                for s in senses:
                    if s.get('id'):
                        self.sense_to_en_lemmas.setdefault(s['id'], set()).add(lemma)
        print('✅ 桥接字典已加载')

    def _load_babelnet_cache(self) -> Dict:
        if os.path.exists(BABELNET_CACHE_FILE):
            with open(BABELNET_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_progress(self, task_id: str):
        if task_id not in self.completed_tasks:
            self.completed_tasks.append(task_id)
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(self.completed_tasks, f, indent=4)

    def _save_temp_results(self):
        summary_df = pd.DataFrame([asdict(r) for r in self.existing_summary])
        summary_df.to_csv(os.path.join(self.temp_result_dir, f'temp_summary_{self.run_ts}.csv'), index=False, encoding='utf-8-sig')
        sample_df = pd.DataFrame([asdict(r) for r in self.existing_samples])
        sample_df['candidate_senses'] = sample_df['candidate_senses'].apply(json.dumps)
        sample_df['request_metadata'] = sample_df['request_metadata'].apply(json.dumps)
        sample_df.to_csv(os.path.join(self.temp_result_dir, f'temp_samples_{self.run_ts}.csv'), index=False, encoding='utf-8-sig')

    def load_data(self, lang: str, level: str=None, data_type: str='real', reference_pool=False) -> List[Dict]:
        base_dir = self.support_dir if reference_pool else self.data_dir
        if data_type == 'real':
            filepath = os.path.join(base_dir, lang, f'sem13_{lang}.csv')
        elif data_type == 'artificial':
            filepath = os.path.join(base_dir, f'artificial_{lang}.csv')
        elif data_type == 'problem':
            filepath = os.path.join(base_dir, f'problem_{lang}.csv')
        else:
            filepath = os.path.join(base_dir, lang, f'sem13_{lang}.csv')
        try:
            df = pd.read_csv(filepath)
            if 'frequency_weight' in df.columns:
                df['frequency_weight'] = pd.to_numeric(df['frequency_weight']).fillna(1.0)
            if 'complexity' in df.columns and level:
                df['complexity'] = df['complexity'].astype(str).str.strip().str.strip('\'"')
                df = df[df['complexity'] == level]
            df['target_word'] = df['sentence'].apply(extract_target_word)
            df = df[df['target_word'] != '']
            data = df.to_dict('records')
            for row in data:
                word_lower = row['target_word'].lower()
                candidates = self.inventory.get(f'{lang}:{word_lower}', [])
                if not candidates:
                    candidates = self.inventory.get(word_lower, [])
                row['candidates'] = candidates
                row['complexity_score'] = self.analyzer.calculate_complexity(row['sentence'])
            return data
        except Exception as e:
            raise RuntimeError(f'加载 {data_type}-{lang}-{level} 数据失败') from e

    def _build_prompt(self, s: Dict, examples: List[Dict], version: str, use_cot: bool=False, data_type: str='real', model_name: str='') -> str:
        target_word = s.get('target_word', '')
        clean_sent = clean_sentence(s.get('sentence', ''))
        candidates = s.get('candidates', [])
        prompt = 'Please act as a Word Sense Disambiguation expert.\n\n'
        prompt += '### Candidate Senses (Dictionary) ###\n'
        for cand in candidates:
            prompt += f"- ID: {cand.get('id')} | Definition: {cand.get('gloss')}\n"
        prompt += '\n'
        if examples:
            if data_type == 'real':
                prompt += '### Contextual Hints (Cross-lingual) ###\n'
                prompt += '[NOTE] The following cross-lingual examples share a highly similar semantic context. Use them to understand the nuanced meaning, but rely STRICTLY on the Dictionary above to select your final ID.\n\n'
            else:
                prompt += '### Reference Examples ###\n'
            for i, ex in enumerate(examples, 1):
                ex_target = ex.get('target_word', extract_target_word(ex.get('sentence', '')))
                if not ex_target:
                    ex_target = 'Unknown'
                prompt += f'Example {i}:\n'
                prompt += f'- Target Word: {ex_target}\n'
                prompt += f'''- Sentence: "{clean_sentence(ex.get('sentence', ''))}"\n'''
                if data_type != 'real':
                    prompt += f"- Correct ID: {ex.get('senseid')}\n"
                prompt += '\n'
        prompt += '### YOUR TASK ###\n'
        prompt += f'**Target Word**: {target_word}\n'
        prompt += f'**Sentence**: {clean_sent}\n\n'
        prompt += '**Instructions**:\n'
        if use_cot:
            prompt += '1. Analyze the context step-by-step to determine the correct sense of the target word.\n'
            prompt += '2. You MUST end your response with the final answer in a JSON block.\n\n'
            prompt += '**Please structure your response exactly like this**:\n'
            prompt += 'Analysis: [Write your step-by-step reasoning here]\n'
            prompt += 'Final Answer: {"sense_id": "the_exact_id_you_chose"}\n'
        else:
            prompt += '1. Identify the correct sense ID directly based on the context.\n'
            prompt += '2. You MUST output ONLY the final answer in a JSON block, without any additional text or analysis.\n\n'
            prompt += '**Please structure your response exactly like this**:\n'
            prompt += '{"sense_id": "the_exact_id_you_chose"}\n'
        return prompt

    def _robust_check(self, resp: str, truth: str) -> bool:
        from evaluation import exact_match
        return exact_match(resp, truth)

    def _prepare_case(self, sample, i, version, monolingual_pool, english_pool,
                      target_lang, data_type, model_key):
        target_word = sample.get('target_word', '')
        complexity_score = sample.get('complexity_score', 0.0)
        cross_lingual_success = False
        used_fallback = False
        retrieve_example_count = 0
        adaptive_k = 3
        use_cot = False
        level_judged = 'simple'
        eng_candidates = []
        final_selected = []
        if version == 'Baseline':
            pool = [x for x in monolingual_pool if x['target_word'].lower() == target_word.lower() and x['sentence'] != sample['sentence']]
            np.random.seed(EXPERIMENT_CONFIG['random_seed'] + i)
            selected = list(np.random.choice(pool, size=min(3, len(pool)), replace=False)) if pool else []
            retrieve_example_count = len(selected)
            prompt = self._build_prompt(sample, selected, version, use_cot=False, data_type=data_type, model_name=model_key)
        elif version in ['Ours(No_CoT)', 'Ours(Fusion)']:
            decision = self.analyzer.get_adaptive_strategy(sample['sentence'])
            adaptive_k = decision['k']
            level_judged = decision['level_judged']
            complexity_score = decision['score']
            if version == 'Ours(No_CoT)':
                decision['use_cot'] = False
            use_cot = decision['use_cot']
            candidate_ids = set()
            for c in sample.get('candidates', []):
                if c.get('id'):
                    candidate_ids.add(str(c.get('id')).strip())
            e5_retrieved = []
            if target_lang == 'en':
                cross_lingual_success = False
            elif data_type != 'real':
                eng_candidates = [x for x in english_pool if bool(gold_ids(str(x.get('senseid'))) & candidate_ids)]
                if eng_candidates:
                    e5_retrieved = self.cl_retriever.retrieve(sample['sentence'], target_lang, eng_candidates, pre_k=EXPERIMENT_CONFIG['e5_retrieve_k'])
                    cross_lingual_success = len(e5_retrieved) > 0
                else:
                    e5_retrieved = []
                    cross_lingual_success = False
            else:
                hard_match_candidates = [x for x in english_pool if bool(gold_ids(str(x.get('senseid'))) & candidate_ids)]
                if hard_match_candidates:
                    eng_candidates = hard_match_candidates
                else:
                    target_lemmas = set()
                    for cid in candidate_ids:
                        target_lemmas.update(self.sense_to_en_lemmas.get(cid, set()))
                    eng_candidates = []
                    if target_lemmas:
                        potential_candidates = [x for x in english_pool if x.get('target_word', '').lower() in target_lemmas]
                        if potential_candidates:
                            real_config = EXPERIMENT_CONFIG['real_data_config']
                            pre_retrieved = self.cl_retriever.retrieve(sample['sentence'], target_lang, potential_candidates, pre_k=real_config['bridge_pre_k'] * 2)
                            target_emb = self.cl_retriever.encode([clean_sentence(sample['sentence'])], target_lang)
                            filtered_candidates = []
                            strict_threshold = max(real_config.get('e5_similarity_threshold', 0.82), 0.86)
                            for cand in pre_retrieved:
                                cand_emb = self.cl_retriever.encode([clean_sentence(cand.get('sentence', ''))], 'en')
                                sim = np.dot(cand_emb, target_emb.T).flatten()[0]
                                if sim >= strict_threshold:
                                    cand['similarity'] = sim
                                    filtered_candidates.append(cand)
                            eng_candidates = filtered_candidates
                if eng_candidates:
                    e5_retrieved = self.cl_retriever.retrieve(sample['sentence'], target_lang, eng_candidates, pre_k=EXPERIMENT_CONFIG['e5_retrieve_k'])
                    cross_lingual_success = len(e5_retrieved) > 0
                else:
                    e5_retrieved = []
                    cross_lingual_success = False
            real_config = EXPERIMENT_CONFIG.get('real_data_config', {})
            fallback_trigger = False
            if data_type == 'real' and real_config.get('fallback_only_when_empty', True):
                fallback_trigger = len(e5_retrieved) == 0
            else:
                fallback_trigger = len(e5_retrieved) == 0
            if fallback_trigger:
                used_fallback = True
                fallback_pool = [x for x in monolingual_pool if x['target_word'].lower() == target_word.lower() and x['sentence'] != sample['sentence']]
                e5_retrieved = fallback_pool
            if data_type == 'real':
                safe_k = min(3, adaptive_k)
                real_alpha = EXPERIMENT_CONFIG['real_data_config']['sampler_alpha']
                if self.real_sampler is None:
                    self.real_sampler = DynamicSemanticSampler(alpha=real_alpha)
                final_selected = self.real_sampler.sample(sample['sentence'], e5_retrieved, k=safe_k)
            else:
                final_selected = self.sampler.sample(sample['sentence'], e5_retrieved, k=adaptive_k)
            retrieve_example_count = len(final_selected)
            prompt = self._build_prompt(sample, final_selected, version, use_cot=use_cot, data_type=data_type, model_name=model_key)
        return dict(prompt=prompt, target_word=target_word, complexity_score=complexity_score,
                    adaptive_k=adaptive_k, use_cot=use_cot, level_judged=level_judged,
                    cross_lingual_success=cross_lingual_success,
                    retrieve_example_count=retrieve_example_count, used_fallback=used_fallback)

    def _test_version(self, model, target_data: List[Dict], version: str, monolingual_pool: List[Dict], english_pool: List[Dict], target_lang: str, model_key: str, level: str, data_type: str) -> Tuple[ExperimentResult, List[SampleLevelResult]]:
        correct = 0
        fallback_count = 0
        total_complexity = 0.0
        n = len(target_data)
        sample_results = []
        if n == 0:
            empty_result = ExperimentResult(experiment_id=f'{model_key}_{data_type}_{target_lang}_{level}_{version}', model_name=model_key, data_source=data_type, target_language=target_lang, data_level=level, system_version=version, accuracy=0.0, improvement=0.0, total_samples=0, correct_samples=0, run_timestamp=self.run_ts, sampler_alpha=EXPERIMENT_CONFIG['real_data_config']['sampler_alpha'] if data_type == 'real' else EXPERIMENT_CONFIG['sampler_alpha'], complexity_strategy='', fallback_count=0, avg_complexity_score=0.0)
            return (empty_result, [])
        print(f'      [Running {version}]...')
        experiment_id = f'{model_key}_{data_type}_{target_lang}_{level}_{version}'
        for i, sample in enumerate(target_data):
            sample_id = str(uuid4())
            case = self._prepare_case(sample, i, version, monolingual_pool, english_pool,
                                      target_lang, data_type, model_key)
            prompt = case['prompt']
            target_word = case['target_word']
            complexity_score = case['complexity_score']
            adaptive_k = case['adaptive_k']
            use_cot = case['use_cot']
            level_judged = case['level_judged']
            cross_lingual_success = case['cross_lingual_success']
            retrieve_example_count = case['retrieve_example_count']
            fallback_count += int(case['used_fallback'])
            total_complexity += complexity_score
            ground_truth = sample.get('senseid', '')
            resp = model.generate_response(prompt, max_tokens=1024)
            is_ok = self._robust_check(resp, ground_truth)
            if is_ok:
                correct += 1
            sample_result = SampleLevelResult(sample_id=sample_id, experiment_id=experiment_id, model_name=model_key, data_source=data_type, target_language=target_lang, data_level=level, system_version=version, target_word=target_word, original_sentence=sample.get('sentence', ''), clean_sentence=clean_sentence(sample.get('sentence', '')), ground_truth_senseid=ground_truth, candidate_senses=sample.get('candidates', []), complexity_score=complexity_score, adaptive_k=adaptive_k, use_cot=use_cot, level_judged=level_judged, cross_lingual_retrieve_success=cross_lingual_success, retrieve_example_count=retrieve_example_count, prompt=prompt if EXPERIMENT_CONFIG['save_prompt'] else None, model_response=resp if EXPERIMENT_CONFIG['save_response'] else None, is_correct=is_ok, sample_run_timestamp=time.strftime('%Y%m%d_%H%M%S'), request_metadata=dict(getattr(model, 'last_call_metadata', {})))
            with (Path(self.output_dir) / 'sample_journal.jsonl').open('a', encoding='utf-8') as journal:
                journal.write(json.dumps(asdict(sample_result), ensure_ascii=False) + '\n')
            sample_results.append(sample_result)
            time.sleep(EXPERIMENT_CONFIG['request_interval'])
        acc = correct / n
        avg_complexity = total_complexity / n if n > 0 else 0.0
        improvement = 0.0 if version == 'Baseline' else None
        summary_result = ExperimentResult(experiment_id=experiment_id, model_name=model_key, data_source=data_type, target_language=target_lang, data_level=level, system_version=version, accuracy=acc, improvement=improvement, total_samples=n, correct_samples=correct, run_timestamp=self.run_ts, sampler_alpha=EXPERIMENT_CONFIG['real_data_config']['sampler_alpha'] if data_type == 'real' else EXPERIMENT_CONFIG['sampler_alpha'], complexity_strategy='fixed_k3_no_cot' if version == 'Baseline' else 'per_sample_see_detail', fallback_count=fallback_count, avg_complexity_score=avg_complexity)
        print(f'    📊 {version} Result: {acc:.1%} ({correct}/{n}) | Fallback: {fallback_count}/{n} | Avg Complexity: {avg_complexity:.2f}')
        return (summary_result, sample_results)

    def _english_pool(self, source):
        from preflight import dataset_path
        if self.allow_missing_english and not dataset_path(self.support_dir, source, 'en').exists():
            print(f'[explicit policy] {source}: no English pool; monolingual fallback enabled')
            return []
        return self.load_data('en', data_type=source, reference_pool=True)

    def inspect_pipeline(self, limit=1):
        import hashlib
        checks = []
        for source in self.data_types:
            english = self._english_pool(source)
            for language in self.target_langs:
                support = self.load_data(language, data_type=source, reference_pool=True)
                for level in self.levels:
                    samples = self.load_data(language, level=level, data_type=source)[:limit]
                    for version in self.versions:
                        for i, sample in enumerate(samples):
                            case = self._prepare_case(sample, i, version, support, english, language, source, '')
                            checks.append({'source': source, 'language': language, 'level': level,
                                           'version': version, 'sample_id': sample.get('sample_id'),
                                           'prompt_sha256': hashlib.sha256(case['prompt'].encode()).hexdigest(),
                                           'examples': case['retrieve_example_count'],
                                           'cross_lingual_retrieval': case['cross_lingual_success'],
                                           'fallback': case['used_fallback']})
        if not checks:
            raise RuntimeError('No selected input samples; no pipeline check exported')
        report = {'purpose': 'pipeline_validation_not_experimental_results', 'model_calls': 0,
                  'metrics_computed': False, 'checks': checks,
                  'configuration': EXPERIMENT_CONFIG, 'selection': self.selection, 'inputs': self.input_manifest}
        path = Path(self.output_dir) / 'pipeline_check.json'
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'真实编码器检索与提示检查完成：{len(checks)} 项；生成模型调用 0 次；未计算指标。')
        print(path)

    def run_experiment(self):
        print('=' * 80 + '\n【优化版：增加消融实验的自适应融合框架】\n' + '=' * 80)
        for data_type in self.data_types:
            print(f"\n{'=' * 60}")
            print(f'📊 当前测试数据类型: {data_type.upper()}')
            print(f"{'=' * 60}")
            english_pool = self._english_pool(data_type)
            if not english_pool:
                print(f'🚨 警告：缺少 {data_type}-EN 数据，该组将完全依赖单语强化策略。')
            else:
                print(f'✅ 成功加载 {len(english_pool)} 条 {data_type}-EN 数据作为跨语言知识库。')
            for model_key in self.models:
                model = self.model_interfaces.get(model_key)
                if model is None:
                    print(f'❌ 模型 {model_key} 未成功初始化，跳过')
                    continue
                for lang in self.target_langs:
                    monolingual_pool = self.load_data(lang, level=None, data_type=data_type, reference_pool=True)
                    for level in self.levels:
                        target_data = self.load_data(lang, level=level, data_type=data_type)
                        if not target_data:
                            print(f'\n▶ 跳过 {data_type}-{lang.upper()}-{level.capitalize()} (无数据)')
                            continue
                        if EXPERIMENT_CONFIG.get('debug_mode', False):
                            target_data = target_data[:EXPERIMENT_CONFIG.get('debug_sample_size', 30)]
                        print(f'\n▶ Testing {data_type}-{lang.upper()}-{level.capitalize()} (N={len(target_data)})')
                        for version in self.versions:
                            task_id = f'{data_type}_{model_key}_{lang}_{level}_{version}'
                            if task_id in self.completed_tasks:
                                print(f'      [跳过 {version}] 已完成')
                                continue
                            summary_result, sample_results = self._test_version(model, target_data, version, monolingual_pool, english_pool, lang, model_key, level, data_type)
                            self.existing_summary.append(summary_result)
                            self.existing_samples.extend(sample_results)
                            self._save_progress(task_id)
                            self._save_temp_results()
        if not self.existing_samples:
            raise RuntimeError('没有完成样本评估；不导出空实验结果。')
        self._calculate_improvement()
        self._save_final_results()

    def _calculate_improvement(self):
        baseline_dict = {}
        for result in self.existing_summary:
            if result.system_version == 'Baseline':
                key = (result.model_name, result.data_source, result.target_language, result.data_level)
                baseline_dict[key] = result.accuracy
        for result in self.existing_summary:
            if result.system_version != 'Baseline':
                key = (result.model_name, result.data_source, result.target_language, result.data_level)
                baseline_acc = baseline_dict.get(key)
                result.improvement = result.accuracy - baseline_acc if baseline_acc is not None else None

    def _save_final_results(self):
        summary_df = pd.DataFrame([asdict(r) for r in self.existing_summary])
        sample_df = pd.DataFrame([asdict(r) for r in self.existing_samples])
        sample_df['candidate_senses'] = sample_df['candidate_senses'].apply(json.dumps)
        sample_df['request_metadata'] = sample_df['request_metadata'].apply(json.dumps)
        final_summary_path = os.path.join(self.output_dir, f'fusion_summary_{self.run_ts}.csv')
        final_sample_path = os.path.join(self.output_dir, f'fusion_sample_detail_{self.run_ts}.csv')
        config_path = os.path.join(self.output_dir, f'config_{self.run_ts}.json')
        summary_df.to_csv(final_summary_path, index=False, encoding='utf-8-sig')
        sample_df.to_csv(final_sample_path, index=False, encoding='utf-8-sig')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump({'experiment_config': EXPERIMENT_CONFIG, 'selection': self.selection, 'evaluation': 'strict_final_json_exact_match_v1', 'inputs': self.input_manifest}, f, indent=4, ensure_ascii=False)
        self._generate_markdown_report(summary_df)
        print(f'\n✅ 实验完成！结果保存路径：')
        print(f'   - 汇总结果（表格用）：{final_summary_path}')
        print(f'   - 样本级详细结果（案例分析用）：{final_sample_path}')
        print(f'   - 实验配置：{config_path}')
        print(f"   - 汇总报告：{os.path.join(self.output_dir, f'report_{self.run_ts}.md')}")

    def _generate_markdown_report(self, summary_df):
        report_path = os.path.join(self.output_dir, f'report_{self.run_ts}.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('# 本次运行结果\n\n')
            f.write('准确率为 0–1 比例；improvement 为准确率差，乘 100 得百分点。\n')
            f.write('无同组 Baseline 时 improvement 为空。不跨模型或数据来源汇总。\n\n')
            f.write(summary_df.to_markdown(index=False) + '\n')

def main():
    global pd, np, SentenceTransformer, UnifiedModelInterface, BABELNET_CACHE_FILE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('local_data/current/data'))
    parser.add_argument('--support-dir', type=Path, default=Path('local_data/current/support_data'))
    parser.add_argument('--inventory', type=Path, default=Path('local_data/current/resources/babelnet_inventory_cache_healed.json'))
    parser.add_argument('--output-dir', type=Path, default=Path('outputs'))
    parser.add_argument('--models', nargs='+', choices=['gpt-4o', 'llama-3.1-70b', 'deepseek-v3'], default=['gpt-4o', 'llama-3.1-70b', 'deepseek-v3'])
    parser.add_argument('--languages', nargs='+', choices=['fr', 'en', 'de', 'es', 'it'], default=['fr', 'en', 'de', 'es', 'it'])
    parser.add_argument('--data-types', nargs='+', choices=['real', 'artificial', 'problem'], default=['real', 'artificial', 'problem'])
    parser.add_argument('--versions', nargs='+', choices=['Baseline', 'Ours(No_CoT)', 'Ours(Fusion)'], default=['Baseline', 'Ours(No_CoT)', 'Ours(Fusion)'])
    parser.add_argument('--levels', nargs='+', choices=['simple', 'medium', 'complex'], default=['simple', 'medium', 'complex'])
    parser.add_argument('--limit', type=int, help='每个评估单元的样本上限；仅用于冒烟检查')
    parser.add_argument('--save-response', action='store_true')
    parser.add_argument('--save-prompt', action='store_true')
    parser.add_argument('--allow-missing-english', action='store_true', help='显式允许缺少英语示例库；该来源改用单语回退并记录配置')
    parser.add_argument('--dry-run', action='store_true', help='真实编码器构建检索与提示；不调用生成模型、不计算准确率')
    parser.add_argument('--check-config', action='store_true', help='只检查选中模型的本地接口配置和凭证是否设置')
    parser.add_argument('--check-only', action='store_true', help='只用标准库校验输入，不加载模型或调用 API')
    args = parser.parse_args()
    from model_interface import load_env_file, configuration, ConfigurationError
    load_env_file()
    paths_file = Path('models/encoder_paths.local.json')
    if paths_file.is_file():
        local_paths = json.loads(paths_file.read_text())
        for key in ('WSD_E5_MODEL', 'WSD_SAMPLER_MODEL'):
            if key in local_paths:
                os.environ.setdefault(key, local_paths[key])
    EXPERIMENT_CONFIG['cross_lingual_model'] = os.environ.get('WSD_E5_MODEL', EXPERIMENT_CONFIG['cross_lingual_model'])
    EXPERIMENT_CONFIG['semantic_sampler_model'] = os.environ.get('WSD_SAMPLER_MODEL', EXPERIMENT_CONFIG['semantic_sampler_model'])
    if args.check_config:
        for alias in args.models:
            try:
                configuration(alias)
            except ConfigurationError as exc:
                parser.exit(2, str(exc) + '\n')
        print('模型身份与本地凭证配置检查通过；未请求服务。')
        return 0
    if args.limit is not None and args.limit < 1:
        parser.error('--limit 必须为正整数')
    errors, manifest = validate_inputs(args.data_dir, args.support_dir, args.inventory, args.data_types, args.languages, require_english=not args.allow_missing_english)
    if errors:
        for error in errors:
            print('[输入检查] ' + error, file=sys.stderr)
        return 2
    print('输入静态校验通过；尚未验证模型服务、凭证或端到端结果。')
    if args.check_only:
        return 0
    if not args.dry_run:
        for alias in args.models:
            try:
                configuration(alias)
            except ConfigurationError as exc:
                parser.exit(2, str(exc) + '\n')
    from importlib.metadata import version
    import pandas as pd
    import numpy as np
    from sentence_transformers import SentenceTransformer
    from model_interface import UnifiedModelInterface
    BABELNET_CACHE_FILE = str(args.inventory)
    EXPERIMENT_CONFIG['save_response'] = args.save_response
    EXPERIMENT_CONFIG['save_prompt'] = args.save_prompt
    EXPERIMENT_CONFIG['debug_mode'] = args.limit is not None
    if args.limit is not None:
        EXPERIMENT_CONFIG['debug_sample_size'] = args.limit
    run_dir = args.output_dir / (time.strftime('%Y%m%d_%H%M%S') + '_' + uuid4().hex[:8])
    runner = ActualFusionRunner(args.data_dir, args.support_dir, str(run_dir), args.data_types,
                               [] if args.dry_run else args.models, args.languages, args.versions, args.levels)
    runner.allow_missing_english = args.allow_missing_english
    runner.selection = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
    runner.selection['package_versions'] = {name: version(name) for name in ('numpy', 'pandas', 'sentence-transformers', 'tabulate', 'torch', 'transformers')}
    runner.selection['python_version'] = sys.version
    setup_file = Path('models/encoder_setup.json')
    if setup_file.is_file():
        runner.selection['encoder_setup'] = json.loads(setup_file.read_text())
    runner.input_manifest = manifest
    if args.dry_run:
        runner.inspect_pipeline(args.limit or 1)
    else:
        runner.selection['model_interfaces'] = {name: model.describe() for name, model in runner.model_interfaces.items()}
        runner.run_experiment()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
