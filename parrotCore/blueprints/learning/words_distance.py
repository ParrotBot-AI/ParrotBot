import pprint

import numpy as np
from scipy.spatial.distance import cosine
from gensim.models import KeyedVectors
import time
import pandas as pd


def calculate_word_distance():
    # Original list of words without "animal"
    df = pd.read_csv("Vocabs.csv")
    words_list = []
    for index, row in df.iterrows():
        words_list.append(
            (int(row['id']), row['word'])
        )

    start = time.time()
    model_path = '/Users/zhilinhe/Desktop/GoogleNews-vectors-negative300.bin.gz'
    word_vectors = KeyedVectors.load_word2vec_format(model_path, binary=True)

    print(time.time() - start)
    count = 0
    # List of words
    word_ids = []
    similarities = []
    for input_tuple in words_list:
        input_id = input_tuple[0]
        input_word = input_tuple[1]
        r = {}
        for compare_tuple in words_list:
            compare_id = compare_tuple[0]
            compare_word = compare_tuple[1]
            if compare_id != input_id:
                try:
                    similarity = word_vectors.similarity(input_word, compare_word)
                    r[compare_id] = similarity
                except:
                    pass

        sorted_similarities = sorted(r.items(), key=lambda x: x[1], reverse=True)
        l = [str(word[0]) for word in sorted_similarities[:10]]
        join_string = ';'.join(l)

        word_ids.append(input_id)
        similarities.append(join_string)
        if count % 100 == 0:
            print(count)
        count += 1

    df = pd.DataFrame({
        "word_id": word_ids,
        "similarity": similarities
    })
    df.to_csv("simi.csv")


if __name__ == "__main__":
    calculate_word_distance()
