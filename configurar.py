#!/usr/bin/env python3
"""Preenche os dados dos autores no artigo e na licença.

Exemplo:

    python3 configurar.py \\
        --autores "Ana Souza" "Bruno Lima" \\
        --instituicao "Instituto de Computação -- Universidade Federal X" \\
        --local "Cidade -- UF -- Brasil" \\
        --emails "ana@uni.br, bruno@uni.br" \\
        --repo https://github.com/usuario/lifi-kem-course

Grava paper/identidade.tex (bloco de título do modelo SBC) e atualiza a linha
de copyright do arquivo LICENSE.  --repo é opcional: sem ele, a Introdução diz
apenas "no repositório que acompanha este artigo".

Todos os autores recebem a mesma instituição.  Para instituições diferentes,
edite paper/identidade.tex depois e use \\inst{2} e \\nextinstitute, como no
exemplo que acompanha o modelo SBC.
"""
from __future__ import annotations

import argparse
import datetime
import os
import re

RAIZ = os.path.dirname(os.path.abspath(__file__))


def tex(texto: str) -> str:
    """Escapa os caracteres que o LaTeX trata como especiais."""
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                 ("#", r"\#"), ("_", r"\_"), ("$", r"\$")):
        texto = texto.replace(a, b)
    return texto


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--autores", nargs="+", required=True, metavar="NOME",
                    help="nomes na ordem em que devem aparecer")
    ap.add_argument("--instituicao", required=True,
                    help="departamento e universidade (primeira linha do endereço)")
    ap.add_argument("--local", default="Brasil",
                    help='segunda linha do endereço, ex.: "Cidade -- UF -- Brasil"')
    ap.add_argument("--emails", required=True,
                    help="e-mails, separados por vírgula")
    ap.add_argument("--repo", default="", help="URL pública do repositório (opcional)")
    args = ap.parse_args()

    autores = ", ".join(f"{tex(a)}\\inst{{1}}" for a in args.autores)
    onde = (f"em \\url{{{args.repo}}}" if args.repo
            else "no repositório que acompanha este artigo")
    conteudo = (
        "% Autores e instituição, no formato do modelo SBC.\n"
        "% Gerado por configurar.py -- prefira rodar o script a editar à mão.\n"
        f"\\newcommand{{\\autores}}{{{autores}}}\n"
        f"\\newcommand{{\\instituicao}}{{{tex(args.instituicao)}\\\\\n"
        f"  {tex(args.local)}\n"
        f"  \\email{{{tex(args.emails)}}}}}\n"
        "% Onde o leitor encontra o código (frase usada no fim da Introdução).\n"
        f"\\newcommand{{\\repositorio}}{{{onde}}}\n")
    caminho = os.path.join(RAIZ, "paper", "identidade.tex")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)
    print("gravado", os.path.relpath(caminho, RAIZ))

    licenca = os.path.join(RAIZ, "LICENSE")
    with open(licenca, encoding="utf-8") as f:
        texto = f.read()
    nomes = " e ".join([", ".join(args.autores[:-1]), args.autores[-1]]
                       if len(args.autores) > 1 else args.autores)
    ano = datetime.date.today().year
    texto = re.sub(r"Copyright \(c\) .*", f"Copyright (c) {ano} {nomes}", texto, count=1)
    with open(licenca, "w", encoding="utf-8") as f:
        f.write(texto)
    print("atualizado LICENSE")
    print("agora rode:  make paper && make check")


if __name__ == "__main__":
    main()
