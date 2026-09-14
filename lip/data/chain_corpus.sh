#!/bin/zsh
# wait for the gold stage, then neighbors, then index
cd /Users/alexjerpelea/MAS-memory-research
while pgrep -f "build_corpus.py gold" > /dev/null; do sleep 15; done
python lip/data/build_corpus.py neighbors > lip/data/corpus_neighbors.log 2>&1
python lip/data/build_corpus.py index > lip/data/corpus_index.log 2>&1
echo CHAIN_DONE >> lip/data/corpus_index.log
