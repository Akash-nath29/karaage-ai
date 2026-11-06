def estimate_tokens(text: str) -> int:
    # ponytail: ~4 chars/token for English. Providers tokenize differently anyway (docs/decisions.md M12);
    # swap in a real tokenizer only if chunk sizes measurably miss their targets.
    return max(1, (len(text) + 3) // 4)
