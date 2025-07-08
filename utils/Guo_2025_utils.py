from rank_bm25 import BM25Okapi
from nltk.tokenize import word_tokenize
import json
# import nltk
# nltk.download('punkt')
# nltk.download('punkt_tab')

config = {
    "read_file": "/data/DataLACP/wangke/recorebench/result/dataset/Guo_rag_2000.jsonl"
}

datas = []
corpus = []
with open(config["read_file"], "r") as f_read:
    for line in f_read:
        data = json.loads(line)
        type = data["cr_type"]
        if type not in [1,2,3]:
            continue
        datas.append(data)
        comment = data["comment"]
        corpus.append(comment)

tokenized_corpus = [word_tokenize(doc) for doc in corpus]
bm25 = BM25Okapi(tokenized_corpus)
total_num = len(datas)
example_num = 3

def get_samples(comment):
    examples = bm25.get_top_n(word_tokenize(comment), tokenized_corpus, n=example_num+1)
    examples_ids = [tokenized_corpus.index(example) for example in examples]
    example_datas = []
    for example_id in examples_ids:
        if datas[example_id]["comment"] != comment:
            example_datas.append(datas[example_id])
    return example_datas[:example_num]

if __name__ == "__main__":
    print(get_samples("Can we get `procs_per_trainer` by interrogating `comm`?"))