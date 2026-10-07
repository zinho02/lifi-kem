PY ?= python3
.PHONY: all test test-full exp1 exp2 data paper check clean

# Roda as duas simulações e gera os dados que o artigo lê.
all: exp1 exp2 data

test:
	$(PY) tests/run_tests.py
test-full:
	$(PY) tests/run_tests.py --full

exp1:
	$(PY) experiments/exp1_kem_cost.py
exp2:
	$(PY) experiments/exp2_arq_position.py
data:
	$(PY) experiments/make_figures_data.py

# Compila paper/main.pdf (precisa de uma instalação de LaTeX).
paper:
	$(MAKE) -C paper

# Confere fórmulas, referências, citações e pendências do artigo.
check:
	$(PY) tests/verificar_artigo.py

clean:
	rm -f results/*.csv paper/data/*.dat paper/data/macros.tex paper/data/table_frag.tex
	$(MAKE) -C paper clean
