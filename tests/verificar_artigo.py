#!/usr/bin/env python3
"""Verificações de consistência do artigo e do repositório.

Uso:  python3 tests/verificar_artigo.py        (ou: make check)

O que é verificado:
  1. toda fórmula em destaque é numerada (não há \\[ \\], $$ nem equation*);
  2. toda fórmula numerada tem rótulo e é citada no texto com \\eqref;
  3. toda figura e toda tabela é citada no texto com \\ref;
  4. toda referência cruzada aponta para um rótulo que existe;
  5. toda citação \\cite{...} existe em refs.bib;
  6. todo valor \\val{...} usado no texto existe em data/macros.tex;
  7. não sobrou nenhum marcador de pendência no repositório;
  8. a identidade dos autores foi preenchida (configurar.py).

Sai com código 0 se tudo estiver em ordem e 1 caso contrário.
"""
from __future__ import annotations

import os
import re
import sys

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ARTIGO = os.path.join(RAIZ, "paper")

PROBLEMAS: list[str] = []


def item(ok: bool, texto: str, detalhe: str = "") -> None:
    print(f"  {'OK   ' if ok else 'FALHA'} {texto}{'  -- ' + detalhe if detalhe else ''}")
    if not ok:
        PROBLEMAS.append(texto)


def sem_comentarios(tex: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", tex)


def fontes_do_artigo() -> list[tuple[str, str]]:
    """main.tex com os \\input expandidos, na ordem em que o LaTeX os lê."""
    saida = []

    def ler(caminho: str) -> None:
        with open(os.path.join(ARTIGO, caminho), encoding="utf-8") as f:
            tex = sem_comentarios(f.read())
        pos = 0
        for m in re.finditer(r"\\input\{([^}]+)\}", tex):
            saida.append((caminho, tex[pos:m.start()]))
            alvo = m.group(1)
            if not alvo.startswith("data/"):
                ler(alvo)
            pos = m.end()
        saida.append((caminho, tex[pos:]))

    ler("main.tex")
    return saida


def main() -> int:
    partes = fontes_do_artigo()
    tudo = "\n".join(t for _, t in partes)

    # ------------------------------------------------------------- fórmulas
    print("Fórmulas")
    sem_numero = re.findall(r"\\\[|\$\$|\\begin\{(?:equation|align|gather)\*\}"
                            r"|\\begin\{displaymath\}", tudo)
    item(not sem_numero, "toda fórmula em destaque é numerada",
         f"{len(sem_numero)} sem número" if sem_numero else "")

    equacoes = []           # (arquivo, rótulo ou None)
    for arquivo, tex in partes:
        for corpo in re.findall(r"\\begin\{equation\}(.*?)\\end\{equation\}", tex, re.S):
            m = re.search(r"\\label\{([^}]+)\}", corpo)
            equacoes.append((arquivo, m.group(1) if m else None))
    item(all(r for _, r in equacoes), "toda fórmula numerada tem rótulo")

    citadas = set()
    for grupo in re.findall(r"\\eqref\{([^}]+)\}", tudo):
        citadas.add(grupo)
    faltam = [r for _, r in equacoes if r and r not in citadas]
    item(not faltam, "toda fórmula numerada é citada no texto (\\eqref)",
         ", ".join(faltam))

    print()
    print(f"  {'nº':>3}  {'rótulo':<14} {'arquivo':<26} citações")
    for n, (arquivo, rotulo) in enumerate(equacoes, 1):
        vezes = len(re.findall(r"\\eqref\{" + re.escape(rotulo or "?") + r"\}", tudo))
        print(f"  {n:>3}  {rotulo or '-':<14} {arquivo:<26} {vezes}")
    print()

    # ----------------------------------------------------- figuras e tabelas
    print("Figuras, tabelas e referências cruzadas")
    rotulos = re.findall(r"\\label\{([^}]+)\}", tudo)
    repetidos = sorted({r for r in rotulos if rotulos.count(r) > 1})
    item(not repetidos, "nenhum rótulo repetido", ", ".join(repetidos))
    usados = set(re.findall(r"\\(?:eq)?ref\{([^}]+)\}", tudo))
    for prefixo, nome in (("fig:", "figura"), ("tab:", "tabela")):
        orfaos = [r for r in rotulos if r.startswith(prefixo) and r not in usados]
        item(not orfaos, f"toda {nome} é citada no texto", ", ".join(orfaos))
    quebradas = sorted(usados - set(rotulos))
    item(not quebradas, "toda referência cruzada tem destino", ", ".join(quebradas))

    # -------------------------------------------------------------- citações
    print("Citações e valores gerados")
    with open(os.path.join(ARTIGO, "refs.bib"), encoding="utf-8") as f:
        chaves = set(re.findall(r"@\w+\{([^,\s]+),", f.read()))
    citacoes = set()
    for grupo in re.findall(r"\\cite\{([^}]+)\}", tudo):
        citacoes.update(c.strip() for c in grupo.split(","))
    ausentes = sorted(citacoes - chaves)
    item(not ausentes, f"as {len(citacoes)} obras citadas existem em refs.bib",
         ", ".join(ausentes))

    caminho_macros = os.path.join(ARTIGO, "data", "macros.tex")
    if os.path.exists(caminho_macros):
        with open(caminho_macros, encoding="utf-8") as f:
            definidos = set(re.findall(r"vlc@(\w+)\\endcsname\{", f.read()))
        pedidos = set(re.findall(r"\\val\{(\w+)\}", tudo))
        item(pedidos <= definidos, f"os {len(pedidos)} valores \\val usados estão em macros.tex",
             ", ".join(sorted(pedidos - definidos)))
    else:
        item(False, "paper/data/macros.tex existe", "rode: make all")

    log = os.path.join(ARTIGO, "main.log")
    if os.path.exists(log):
        with open(log, encoding="latin-1") as f:
            texto_log = f.read()
        ruins = re.findall(r"(?:Reference|Citation) `[^']+' .*undefined|Overfull \\hbox", texto_log)
        item(not ruins, "última compilação sem referências indefinidas nem linhas estouradas",
             f"{len(ruins)} aviso(s) em paper/main.log" if ruins else "")

    # ------------------------------------------------------------ pendências
    print("Pendências")
    # Sem re.I: em português, "todo" e "método" são palavras comuns.
    marcadores = re.compile(
        r"\bTODO\b|\bFIXME\b|\bTBD\b|\bXXX\b|\?\?\?|[Ll]orem ipsum"
        r"|\[course name\]|\[university\]|\[Author Name\]|First Author"
        r"|<repo-url>|\bA FAZER\b|\bPENDENTE\b")
    achados = []
    ignorar_dirs = {".git", "__pycache__", "results"}
    extensoes = (".py", ".tex", ".md", ".bib", ".txt", ".csv", ".sty", "Makefile", "LICENSE")
    eu = os.path.abspath(__file__)
    for pasta, dirs, arquivos in os.walk(RAIZ):
        dirs[:] = [d for d in dirs if d not in ignorar_dirs]
        for nome in arquivos:
            caminho = os.path.join(pasta, nome)
            if not nome.endswith(extensoes) or os.path.abspath(caminho) == eu:
                continue
            if nome in ("sbc-template.sty", "caption2.sty", "sbc.bst"):
                continue                      # arquivos do modelo SBC, sem alterações
            with open(caminho, encoding="utf-8", errors="replace") as f:
                for n, linha in enumerate(f, 1):
                    if marcadores.search(linha):
                        achados.append(f"{os.path.relpath(caminho, RAIZ)}:{n}")
    item(not achados, "nenhum marcador de pendência no repositório", ", ".join(achados[:8]))

    with open(os.path.join(ARTIGO, "identidade.tex"), encoding="utf-8") as f:
        identidade = f.read()
    item("Primeiro Autor" not in identidade and "exemplo.br" not in identidade,
         "autores e instituição preenchidos",
         "" if "Primeiro Autor" not in identidade else "rode: python3 configurar.py --help")

    print()
    if PROBLEMAS:
        print(f"{len(PROBLEMAS)} problema(s) encontrado(s).")
        return 1
    print("Tudo em ordem.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
