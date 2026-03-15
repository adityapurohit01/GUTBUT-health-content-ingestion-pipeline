import re

def chunk_text(text: str, words_per_chunk: int = 350) -> list[str]:
    """
    Chunks text into roughly `words_per_chunk` sized segments,
    while preserving sentence boundaries.
    """
    if not text.strip(): return []
    
    sentences = re.split(r'(?<=[.!?]) +', text.strip())
    
    chunks = []
    current_chunk = []
    current_word_count = 0
    
    for sentence in sentences:
        words = sentence.split()
        word_count = len(words)
        
        if current_word_count + word_count > words_per_chunk and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_word_count = word_count
        else:
            current_chunk.append(sentence)
            current_word_count += word_count
            
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    return chunks
