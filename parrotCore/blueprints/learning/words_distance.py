import numpy as np
from scipy.spatial.distance import cosine
from gensim.models import KeyedVectors
import time

def calculate_word_distance(input_word):
    # Original list of words without "animal"
    start = time.time()
    model_path = '/Users/zhilinhe/Desktop/GoogleNews-vectors-negative300.bin.gz'
    word_vectors = KeyedVectors.load_word2vec_format(model_path, binary=True)

    print(time.time() - start)

    # List of words
    words = ["apple", "banana", "orange", "grape", "cherry", "monkey", "whales", "zebra", "sheep"]

    # Compute similarities with the input word "animal"
    similarities = {word: word_vectors.similarity(input_word, word) for word in words}

    # Sort words based on their similarity to "animal"
    sorted_similarities = sorted(similarities.items(), key=lambda x: x[1], reverse=True)

    # Get the top 4 similar words
    top_4_similar_words = sorted_similarities[:4]

    print(time.time() - start)
    print(top_4_similar_words)

calculate_word_distance('goat')


