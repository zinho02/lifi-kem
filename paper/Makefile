# Compila o artigo.  Para outro compilador:  make PDFLATEX="pdflatex -fmt=..."
MAIN     = main
PDFLATEX ?= pdflatex
.PHONY: all clean
all: $(MAIN).pdf
$(MAIN).pdf: $(MAIN).tex identidade.tex refs.bib sections/*.tex figures/*.tex \
             data/macros.tex data/table_frag.tex sbc-template.sty sbc.bst
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error $(MAIN) >/dev/null
	bibtex $(MAIN)
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error $(MAIN) >/dev/null
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error $(MAIN) >/dev/null
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error $(MAIN) | tail -2
clean:
	rm -f $(MAIN).aux $(MAIN).bbl $(MAIN).blg $(MAIN).log $(MAIN).out $(MAIN).pdf
