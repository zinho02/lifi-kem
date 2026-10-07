# Quanto Custa uma Troca de Chaves Pós-Quântica em um Enlace Li-Fi para IoT?

Artigo de disciplina, com todo o código que o sustenta. Um nó sensor de IoT
combina uma chave com o ponto de acesso usando um KEM padronizado pelo NIST
(ML-KEM, FIPS 203) sobre um enlace óptico simulado. A pergunta é uma só: o
custo é dominado pelo **processamento** ou pela **transmissão**?

Resposta: pela transmissão, com ampla margem.

| resultado | valor |
|---|---|
| taxa em que transmitir o ML-KEM-512 leva o mesmo tempo que calculá-lo | **3,10 Mbit/s** (768: 2,75; 1024: 2,41) |
| processamento no nó, ML-KEM-512 contra X25519 (Cortex-M4) | **4,9 ms contra 6,5 ms**: o ML-KEM é *mais barato* |
| tempo da troca ao longo da sala, a 400 kbit/s | **42 ms sob a luminária, 1214 ms junto à parede** (29 vezes) |
| melhor tamanho de fragmento, enlace bom e enlace ruim | **128 B e 32 B** |

O artigo compilado está em `paper/main.pdf` (27 páginas, modelo da SBC, em
português, com *abstract* em inglês).

## Início rápido

```bash
pip install -r requirements.txt
python3 tests/run_tests.py      # deve terminar com "all tests passed"
make all                        # roda as duas simulações, cerca de 10 s
make paper                      # compila paper/main.pdf
make check                      # confere fórmulas, referências e pendências
```

## Estrutura

```
src/vlckem/      mlkem (FIPS 203), optics, modulation, link, handshake
experiments/     exp1_kem_cost.py, exp2_arq_position.py,
                 make_figures_data.py, mcu_profile.py
tarefas/         tarefas passo a passo para o segundo autor, com gabarito
tests/           run_tests.py, vetor acumulado do C2SP, verificar_artigo.py
paper/           main.tex, sections/, figures/, data/, modelo da SBC
bench/           exemplo de arquivo de tempos medidos em hardware
configurar.py    preenche autores e instituição
```

O texto do artigo, as tarefas e esta documentação estão em português. O
código-fonte, seus comentários e as mensagens dos scripts de simulação estão em
inglês, como é usual em código.

**Segundo autor: comece por `tarefas/README.md`.** São sete tarefas, cerca de
12 horas no total, cada uma com algo para executar e algo para entregar. As
respostas esperadas estão em `tarefas/GABARITO.md`.

## Autores e instituição

O bloco de título do modelo SBC (autores, instituição e e-mails) fica em um
único arquivo, `paper/identidade.tex`, gravado por um comando:

```bash
python3 configurar.py \
    --autores "Nome do Primeiro Autor" "Nome do Segundo Autor" \
    --instituicao "Departamento -- Universidade" \
    --local "Cidade -- UF -- Brasil" \
    --emails "primeiro@uni.br, segundo@uni.br"
make paper && make check
```

O mesmo comando atualiza a linha de copyright do `LICENSE`. A opção `--repo`
acrescenta ao artigo o endereço público do repositório. `make check` acusa se a
identidade ainda não foi preenchida.

## Validação

A criptografia é conferida com vetores oficiais, e não apenas consigo mesma.
`src/vlckem/mlkem.py` reproduz o vetor acumulado do C2SP/CCTV para o ML-KEM-768
em 10 000 iterações (resumo `8a518cc63da366322a8e7a818c7a0d63`), incluindo os
caminhos de rejeição implícita:

```bash
python3 tests/run_tests.py --full   # cerca de 1 min
```

A implementação **não é de tempo constante** e nunca deve proteger dados reais.
Ela existe para que a simulação movimente chaves e textos cifrados genuínos.

## Reprodutibilidade

Todo número do artigo vem de `paper/data/macros.tex`, gerado por
`experiments/make_figures_data.py` a partir dos CSVs de `results/`, e entra no
texto com `\val{Nome}`. Nenhum resultado é digitado à mão no manuscrito,
inclusive o exemplo passo a passo da Tabela 7; assim, o texto não consegue
divergir dos dados. As figuras do pgfplots leem os arquivos `.dat` diretamente.
O gerador já escreve os números com vírgula decimal.

## Fórmulas do artigo

Todas as fórmulas em destaque são numeradas, citadas no texto pelo número e
acompanhadas da fonte. `make check` confere as duas primeiras condições
automaticamente e imprime quantas vezes cada fórmula é citada.

| nº | fórmula | origem | usada em |
|---:|---|---|---|
| 1 | tempo a partir da contagem de ciclos | definição; contagens de Kannwischer *et al.* (pqm4) | Seções 2.1, 3.5, 5.3; Tabela 7 |
| 2 | ganho do canal lambertiano | Kahn e Barry (1997); Komine e Nakagawa (2004) | Seções 2.3, 5.1 |
| 3 | ordem lambertiana | Kahn e Barry (1997) | Seção 2.3 |
| 4 | SNR em cada posição | Kahn e Barry (1997) | Seções 2.3, 2.5, 5.1; Figura 3 |
| 5 | simetria hermitiana | Dissanayake e Armstrong (2013) | Seção 2.4; Figura 2 |
| 6 | bits por símbolo DCO-OFDM | Dissanayake e Armstrong (2013) | Seções 2.4, 5.1; Figura 2 |
| 7 | SNR efetiva com ceifamento | Dimitrov e Haas (2013) | Seções 2.4, 2.5, 5.1 |
| 8 | taxa de erro de bit da QAM | Proakis e Salehi (2008) | Seções 2.5, 5.1; Figura 3 |
| 9 | sobrevivência de um fragmento | Bertsekas e Gallager (1992) | Seções 2.6, 5.3, 6.4; Tabela 7 |
| 10 | desigualdade de Mosca | Mosca (2018) | Seção 3.3 |
| 11 | sistema linear de exemplo | exemplo didático do artigo | Seção 3.5 |
| 12 | problema MLWE | FIPS 203 | Seção 3.5 |
| 13 | tamanho da chave de encapsulamento | FIPS 203 | Seção 3.5 |
| 14 | tamanho do texto cifrado | FIPS 203 | Seção 3.5 |
| 15 | derivação da chave de sessão | NIST SP 800-227 | Seção 5.2; Figura 4 |
| 16 | transmissões esperadas com ARQ | deduzida da Eq. 9; Bertsekas e Gallager (1992) | Seções 5.3, 6.1; Tabela 7 |
| 17 | tempo de transmissão | definição do artigo | Seção 5.3; Tabelas 7 e 8 |
| 18 | tempo total da troca | definição do artigo | Seções 5.3, 6.2; Figuras 5 e 6; Tabelas 7 e 9 |
| 19 | taxa de cruzamento | deduzida da Eq. 18 | Seções 5.3, 6.1; Figura 5; Tabelas 7 e 8 |

## Compilar o artigo

O artigo usa o modelo de artigos da SBC: `sbc-template.sty`, `sbc.bst` e
`caption2.sty` estão em `paper/`, sem alterações, exatamente como a SBC os
distribui. O texto tem oito seções: Introdução; Fundamentos de Li-Fi para a
Internet das Coisas; Fundamentos da Troca de Chaves Pós-Quântica; Trabalhos
Relacionados; Cenário e Método; Resultados (com um exemplo passo a passo e
diretrizes práticas); Limitações; Conclusão. As quatro primeiras ficam em
`paper/sections/`; as demais, em `main.tex`.

É preciso uma instalação de LaTeX com `pgfplots`, `booktabs`, `titlesec` e
`babel`. Para a hifenização correta em português, instale também o suporte ao
idioma (no Debian e no Ubuntu, o pacote `texlive-lang-portuguese`). Sem ele, o
artigo compila do mesmo jeito, apenas com a hifenização menos precisa.

O modelo da SBC pede resumo e *abstract* de até dez linhas cada; os dois
respeitam esse limite. O modelo usa citações no formato autor-ano, como
[Kahn and Barry 1997], geradas pelo `sbc.bst`.

## Tempos medidos em hardware real

O piso de processamento usa contagens de ciclos publicadas para o Cortex-M4
(pqm4; Chen e Chou). Para substituí-las pelas de uma placa própria:

```bash
python3 experiments/mcu_profile.py --profile bench/example_esp32.csv --clock 240e6
```

`bench/example_esp32.csv` mostra o formato do arquivo, com valores
ilustrativos. Contagens de ciclos não se transferem entre arquiteturas: números
medidos devem aparecer como uma coluna separada, com o nome do chip, a
frequência, o compilador e o nível de otimização. Atenção também ao fato de que
o ML-KEM do FIPS 203 usa SHAKE (SHA-3), que o acelerador de hash do ESP32 não
implementa; os ganhos publicados para o "Kyber" no ESP32 referem-se à variante
"90s", baseada em AES e SHA-2.

## Limitações

É um estudo por simulação. O canal é de visada direta, com receptor parado e
voltado para cima, sem reflexões nas paredes, inclinação ou mobilidade. Nenhum
hardware foi medido. A troca de chaves estabelece sigilo, mas não identidade:
acrescentar assinaturas pós-quânticas mais do que dobraria os tempos de
transmissão.

## Licença

Código sob a licença MIT (`LICENSE`); texto e figuras do artigo sob CC BY-NC 4.0.
Os arquivos do modelo (`sbc-template.sty`, `sbc.bst`, `caption2.sty`) pertencem
aos seus autores e são distribuídos pela SBC.
