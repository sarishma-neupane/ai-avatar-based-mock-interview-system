"""
SBERT Service for Semantic Similarity
Uses sentence-transformers to calculate similarity between user answer and ideal answer.

Key improvements:
  1. Question-echo penalty  – if the user's answer is essentially a paraphrase/repeat of the
     *question* (not the ideal answer) the score is heavily penalised.
  2. Length / information ratio – very short answers that happen to share topic words with
     the ideal answer are capped at a lower ceiling before the cosine score is accepted.
  3. Asymmetric comparison – only measures how well the user covered the ideal answer's
     concepts, not the other way around (prevents topic-keyword inflation).
"""

import re
import logging
import numpy as np
import torch
from sentence_transformers import SentenceTransformer, util

logger = logging.getLogger(__name__)

# Global singleton model – loaded once, reused for all requests
_sbert_model = None


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "on", "at", "by", "for", "with", "about",
    "against", "between", "into", "through", "during", "before", "after",
    "above", "below", "from", "up", "down", "out", "off", "over", "under",
    "again", "further", "then", "once", "and", "but", "or", "nor", "so",
    "yet", "both", "either", "neither", "not", "only", "own", "same",
    "than", "too", "very", "s", "t", "just", "don", "that", "this",
    "it", "its", "i", "me", "my", "myself", "we", "our", "ours",
    "ourselves", "you", "your", "yours", "yourself", "he", "him", "his",
    "himself", "she", "her", "hers", "herself", "they", "them", "their",
    "theirs", "themselves", "what", "which", "who", "whom",
}


def _content_words(text: str) -> set:
    """Return meaningful (non-stopword) words from *text*."""
    # Included digits to capture things like 'Python 3', '2D arrays', etc.
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def _word_overlap_ratio(set_a: set, set_b: set) -> float:
    """Jaccard-style overlap capped to the smaller set."""
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / min(len(set_a), len(set_b))


# ──────────────────────────────────────────────────────────────────────────────
# Service
# ──────────────────────────────────────────────────────────────────────────────

class SBERTService:
    # Balanced penalty weight – reduced because we now verify suspicious echoes with LLM.
    ECHO_PENALTY_WEIGHT = 0.35   # raw_score × (1 – ratio × weight)

    # Minimum word count for an answer to carry full weight
    MIN_MEANINGFUL_WORDS = 4

    def __init__(self, model_name: str = "all-mpnet-base-v2"):
        global _sbert_model
        if _sbert_model is None:
            logger.info(f"Loading SBERT model: {model_name} ...")
            try:
                _sbert_model = SentenceTransformer(
                    model_name,
                    # Removing explicit device="cpu" to avoid meta-tensor copy errors on some versions.
                    # It will default to CPU if no GPU is available.
                )
                if hasattr(_sbert_model, 'to'):
                    _sbert_model.to('cpu')
                logger.info("SBERT model loaded successfully on cpu")
            except Exception as e:
                logger.error(f"Failed to load primary SBERT model: {e}")
                try:
                    import os
                    cache_dir = os.path.join(
                        os.path.expanduser("~"), ".cache", "sentence_transformers"
                    )
                    os.makedirs(cache_dir, exist_ok=True)
                    fallback = "all-MiniLM-L6-v2"
                    _sbert_model = SentenceTransformer(
                        fallback,
                        cache_folder=cache_dir,
                    )
                    if hasattr(_sbert_model, 'to'):
                        _sbert_model.to('cpu')
                    logger.info("SBERT fallback model loaded successfully")
                except Exception as retry_err:
                    raise RuntimeError(
                        f"Could not initialise SBERT model: {retry_err}"
                    ) from retry_err

        # Warmup so the first real request is fast
        if _sbert_model:
            try:
                _sbert_model.encode(
                    ["warmup"], convert_to_tensor=True, device="cpu"
                )
                logger.info("SBERT warmup complete.")
            except Exception:
                pass

        self.model = _sbert_model

    def _fallback_similarity_llm(self, user_text: str, ideal_texts: list[str], question_text: str = "") -> tuple[float, str]:
        """Use Gemini to calculate similarity if SBERT fails or for verification."""
        try:
            from gemini.gemini_service import GeminiService
            gemini = GeminiService()
            result = gemini.calculate_semantic_similarity_llm(user_text, ideal_texts, question_text)
            return result.get('score', 0.0), result.get('best_match', ideal_texts[0] if ideal_texts else "")
        except Exception as e:
            logger.error(f"LLM Fallback similarity failed: {e}")
            return 0.0, (ideal_texts[0] if ideal_texts else "")


    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def calculate_similarity(
        self,
        user_text: str,
        ideal_texts: list | str,
        question_text: str = "",
        force_llm: bool = False,
    ) -> tuple[float, str]:
        """
        Calculate semantic similarity between *user_text* and the best entry
        in *ideal_texts*.

        Now includes a 'Contextual Validator' (LLM) for ambiguous cases.
        """
        if not user_text or not ideal_texts:
            logger.warning("Empty input to calculate_similarity")
            return 0.0, ""

        if isinstance(ideal_texts, str):
            ideal_texts = [ideal_texts]

        # Filter out empty / placeholder entries
        ideal_texts = [
            t for t in ideal_texts
            if t and t.strip() and t.strip() not in ("Evaluation Pending", "None")
        ]
        if not ideal_texts:
            logger.warning("No valid ideal_texts after filtering")
            return 0.0, ""

        try:
            # ── 1. Encode ──────────────────────────────────────────────────
            user_emb = self.model.encode(
                user_text,
                convert_to_tensor=True,
                device="cpu",
                normalize_embeddings=True,
            )
            ideal_embs = self.model.encode(
                ideal_texts,
                convert_to_tensor=True,
                device="cpu",
                normalize_embeddings=True,
            )

            # ── 2. Cosine similarity vs every ideal answer ─────────────────
            cosine_scores = util.cos_sim(user_emb, ideal_embs)  # shape (1, N)
            best_idx = int(torch.argmax(cosine_scores).cpu().item())
            raw_score = float(cosine_scores[0][best_idx].cpu().item())
            best_text = ideal_texts[best_idx]

            # ── 3. Echo Detection & preliminary score ──────────────────────
            echo_penalty = 0.0
            overlap_with_question = 0.0
            overlap_with_ideal = 0.0
            ua_content_only = set()

            if question_text.strip():
                clean_u = re.sub(r'[^a-z0-9]', '', user_text.lower())
                clean_q = re.sub(r'[^a-z0-9]', '', question_text.lower())
                
                # A. Strict Repeat Check
                if len(clean_u) > 5 and (clean_u == clean_q or clean_u in clean_q):
                    logger.warning("[SBERT] HARD KILL: Question repeat detected.")
                    return 0.0, best_text

                q_words  = _content_words(question_text)
                ua_words = _content_words(user_text)
                id_words = _content_words(best_text)

                overlap_with_question = _word_overlap_ratio(ua_words, q_words)
                overlap_with_ideal    = _word_overlap_ratio(ua_words, id_words)
                ua_content_only = ua_words - q_words

                # B. Contentless Echo Check (e.g. "To do element wise multiplication I would...")
                if overlap_with_question > 0.85 and len(ua_content_only) < 3:
                    logger.warning(f"[SBERT] HARD KILL: High echo ({overlap_with_question:.2f}) with minimal new content.")
                    return 0.0, best_text

                echo_signal = max(0.0, overlap_with_question - (overlap_with_ideal * 1.2))
                echo_penalty = self.ECHO_PENALTY_WEIGHT * echo_signal

            final_sbert_score = raw_score * (1.0 - max(0, echo_penalty))

            # ── 4. Length / Sanity Caps ────────────────────────────────────
            ua_word_count = len(user_text.split())
            if ua_word_count < 2:
                final_sbert_score = min(final_sbert_score, 0.1)
            elif ua_word_count < self.MIN_MEANINGFUL_WORDS:
                final_sbert_score = min(final_sbert_score, 0.40 + 0.10 * ua_word_count)

            final_sbert_score = max(0.0, min(1.0, final_sbert_score))

            # ── 5. HYBRID VALIDATION: Trigger LLM for Ambiguous Cases ──────
            # This is the "Fix Once and For All" – if SBERT is in a region of doubt, 
            # or suspects an echo, we let Gemini judge the contextual meaning.
            
            is_suspicious = (echo_penalty > 0.1) or (overlap_with_question > 0.6)
            is_ambiguous = (0.25 <= final_sbert_score <= 0.75)
            
            if force_llm or is_suspicious or is_ambiguous:
                logger.info(f"[SBERT] Triggering LLM Verification (score={final_sbert_score:.2f}, echo={echo_penalty:.2f})")
                llm_score, llm_best_text = self._fallback_similarity_llm(user_text, ideal_texts, question_text)
                
                # The LLM is the final authority on contextual meaning
                # We use it if it confirms a high score or confirms a zero for echoes.
                if llm_score < 0.1 and overlap_with_question > 0.7:
                     logger.info("[SBERT] LLM confirmed echo. Score -> 0.0")
                     return 0.0, best_text
                
                if llm_score > final_sbert_score + 0.15:
                     logger.info(f"[SBERT] LLM promoted score from {final_sbert_score:.2f} to {llm_score:.2f} (Recognized Meaning)")
                
                return llm_score, llm_best_text

            # If not ambiguous, SBERT is usually correct and faster
            logger.info(f"[SBERT] Confidence high. Raw={raw_score:.2f}, Final={final_sbert_score:.2f}")
            return final_sbert_score, best_text

        except Exception as exc:
            logger.error(f"SBERT Critical Failure: {exc}")
            return self._fallback_similarity_llm(user_text, ideal_texts, question_text)

