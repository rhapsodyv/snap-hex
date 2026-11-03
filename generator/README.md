# SnapHex — gerador e notas de projeto

O `gridv8` do Fusion recriado com [build123d](https://build123d.readthedocs.io)
(Python sobre o kernel OpenCascade). O Fusion fica para montagem e visualização,
importando os STEP gerados.

A grid fica embaixo do deck da Voron e os eletrônicos ficam pendurados nela:
- **andar de baixo** (z −2,9..2,9, canal em z=0): os mount plugs entram por baixo em qualquer célula;
- **andar de cima** (até z=7): só nas células ao longo das emendas, maciço, com as cavilhas chatas
  que juntam os 4 quadrantes, e nos 4 suportes com rasgo que parafusam no deck;
- **borda** de 7 mm com 16 furos M5 laterais que vão no rasgo interno dos perfis 2020.

## Rodar

```bash
python3 -m venv .venv && .venv/bin/pip install build123d matplotlib scipy
.venv/bin/python generator/build.py  # gera tudo em out/ (~1 min, quadrantes em paralelo)
.venv/bin/python generator/validate_gridv8.py  # compara com cortes tirados do gridv8
```

`build.py BL` gera só um quadrante; `--assembly` gera também `out/assembly.step` (~200 MB).

## Emenda entre quadrantes (em teste)

`seam_style` em `params.py` escolhe como os quadrantes se ligam:

- `"v8"` (atual, igual ao gridv8): anéis do andar de cima abertos na emenda e plugs de união
  com abas rígidas em cima. Frágil (a grid é quem flexiona, no pescoço de ~0,6 mm do canal) e
  não segura flexão, por isso o centro fica bambo.
- `"dovetail"`: a faixa de células da emenda fica maciça do lado do painel (z 3,2–7,0, 0,3 mm
  acima de um mount plug encaixado), virando uma cruz rígida pelo centro. Em cada fileira uma
  chave maciça de rabo de andorinha atravessa a emenda, pressionada pelo lado do painel. As
  paredes laterais do encaixe fecham a 10° e as da chave a 5°: a chave fica justa na boca e a
  base dela, mais larga, fica presa embaixo — entra e sai vencendo ~0,24 mm por lado
  (`key_angle` regula; `build.py --coupons` gera chaves de 3°, 5° e 7° para testar). O lado dos
  eletrônicos fica livre para mount plugs.
  ~+21% de material por quadrante, mais 39 chaves.
  `seam_bottom_link = True` acrescenta plugs duplos por baixo (ligação do lado dos eletrônicos),
  caso o teste mostre que a emenda ainda abre ao puxar.

- `"spline"` (padrão; lâmina de 2,0 mm testada — 1,9 fica frouxa, 2,1 também serve): mesma faixa maciça, mas cada fileira é ligada por uma cavilha
  chata (lâmina 2×8×18 mm) num rasgo horizontal no meio dos blocos. Como o perfil já prende os
  quadrantes no plano, a emenda só precisa impedir o movimento vertical, e a folga vertical da
  lâmina é só a folga do rasgo (±0,1 mm). As lâminas correm em x na emenda vertical e em y na
  horizontal; montagem: juntar trás-esq + trás-dir e frente-esq + frente-dir deslizando em x,
  depois as duas metades deslizando em y.

`build.py --coupons` gera os corpos de prova, cada um também montado num STEP
(`*_assembly.step`) para abrir no Fusion:

| teste | imprimir |
|---|---|
| só a emenda (2 células) | `spline_pair_L`, `spline_pair_R`, `spline_1.9mm` / `_2.0mm` / `_2.1mm` (espessura gravada) |
| 3×3 células, cavilha | `coupon_spline_L`, `coupon_spline_R`, 3× `spline` |
| 3×3 células, gridv8 | `coupon_v8_L`, `coupon_v8_R`, 3× `union_plug` |

Tudo imprime como sai do arquivo, com a base (z mais baixo) na mesa.

## Teste do mount plug

`build.py --mounts` gera as variantes da vez (`mount_batch` em `params.py`; letra gravada no
topo e, espelhada, na base, para aparecer também quando a peça é cortada), a tirinha de células (`mount_test_cells`) e o conjunto montado
(`mount_test_assembly.step`). Com `mount_open_top`, cada plug de barra do lote sai também
como `mount_plug_X_open`: cortado no teto do bolso, com as molas à vista (a letra vai na base).
Todas as variantes ficam em `mount_variants`:

| plug | o que muda | resultado |
|---|---|---|
| `mount_plug_A` | como no gridv8 (referência) | |
| `mount_plug_C` | A + flanco de carga do ressalto reto a 30° da horizontal (~2× mais força para sair, entrada igual); **imprime de cabeça para baixo** (o arquivo já sai virado) | segura mais que o A, mas estraga a trava ao arrancar: descartado. A carga máxima cai na quina viva onde a reta de 30° encontra a ponta |
| `mount_plug_E` | a trava é uma barra de quase a face inteira, empurrada por uma mola em zigue-zague atrás dela (3 trechos de 0,6 mm que encurtam em direção ao centro, bolsos separados por parede de 0,8 mm); ressalto ao longo da barra, recuado 0,2 mm: a barra recua 0,85 mm (A: 1,05); contato ~4–6 mm por face | melhor que o A |
| `mount_plug_F` | E + flanco de carga a 30° do C; **imprime de cabeça para baixo** | melhor que o A, mas o flanco de 30° fica de fora pelo mesmo motivo do C |
| `mount_plug_G` | E com barra e mola da altura da lâmina interna do gridv8 (1,2–4,5 em vez de 1,4–4,3) | |
| `mount_plug_H` | G + vãos da mola 0,6/0,5/0,4/0,5 (barra→fundo) em vez de 0,5: o 2º trecho passa a trabalhar tanto quanto os outros | |
| `mount_plug_I` | H + bolso mais alto (paredes de cima e de baixo com 0,8 em vez de 1,0) e barra/mola de 1,0–4,7 | muito bom: entra, fica e sai firme; depois de vários coloca-tira as pontas dos ressaltos não esbranquiçaram |
| `mount_plug_J` | H com ressalto simétrico de flancos retos a 40° e ponta redonda r0,5, sem quina nenhuma | J, K e L bons e difíceis de diferenciar; nenhum esbranquiçou depois de vários coloca-tira |
| `mount_plug_K` | J com flancos a 45° | |
| `mount_plug_L` | K com ponta r0,8 | |
| `mount_plug_M`, `_N`, `_O` | mola e bolso do I com as pontas de J, K e L | N e O sem fadiga nas molas; O sem marca nos ressaltos, N com marca leve. Puxando só pelo parafuso, o topo e a base dos bolsos deformam |
| `mount_plug_P` | O com a barra apoiando só nas pontas (1 mm de cada lado, junto às colunas); o meio da barra fica com 0,6/0,7 de folga até a base e o topo e imprime como ponte entre as pontas | **escolhido**: ótimo, sem deformar topo e base |
| `mount_plug_Q` | P com topo e base de 1,0 (mola da altura do H: ~11% menos força) | |

O canal da grid não muda: a borda arredondada dele encosta em qualquer ângulo de flanco.

`spring_model.py` compara as travas num modelo de vigas (lâminas e trechos de mola encostando uns
nos outros quando os vãos fecham). Os números servem para comparar variantes; o E do ABS é
estimado. A força é a da mola para recolher a trava; com o mesmo ressalto, a força para arrancar
acompanha ela.

| trava | curso | força por trava | maior deformação | com 0,1 mm a mais de curso |
|---|---|---|---|---|
| A, C | 1,05 | 2,6 N | 2,4% (lâmina externa) | 2,8 N, 2,7% |
| E, F | 0,85 | 4,2 N (1,6× A) | 2,1% | 6,2 N, 2,8% |
| G | 0,85 | 4,8 N (1,9× A) | 2,1% | 7,1 N, 2,8% |
| H | 0,85 | 5,9 N (2,3× A) | 2,2% | 8,1 N, 2,9% |
| I | 0,85 | 6,6 N (2,6× A) | 2,2% | 9,1 N, 2,9% |

No fim do curso os trechos da mola do E/F já encostam uns nos outros; é isso que a deixa mais
dura que a soma das vigas. Mais saliência no ressalto aumenta a força, mas a deformação sobe
junto, e com a saliência do A (0,2 a mais) a barra encosta na mola e o conjunto vira bloco
(~29 N). A força a mais de G–I vem de altura (força proporcional à altura, deformação igual) e
de dividir melhor a flexão entre os trechos, sempre abaixo da deformação do A.

O ressalto em S do gridv8, como desenhado, tem um trecho a ~20° da horizontal justo onde ele
encosta nas bordas do canal; impresso em camadas de 0,2 ele vira um dente em degraus, e o teste
(C segurando mais que o A) mostra que esse trecho não existe na peça. Por isso o modelo de
arrancar (`spring_model.py`, segunda tabela) só vale para os ressaltos de flanco reto:

| trava | mola recuada encaixada | para arrancar (máx.) | contato máx. no ressalto |
|---|---|---|---|
| C (30° só embaixo, mola do A) | 0,33 | 8,4 N | 8,0 N, na quina da ponta |
| J (40°, r0,5, mola do H) | 0,21 | 4,6 N | 6,5 N |
| K (45°, r0,5) | 0,25 | 4,6 N | 6,5 N |
| L (45°, r0,8) | 0,37 | 4,1 N | 6,1 N |
| M, N, O (mola do I) | 0,21 / 0,25 / 0,37 | 5,1 / 5,2 / 4,6 N | 7,2 / 7,3 / 6,9 N |

Com a mola progressiva, o máximo para arrancar acontece no fim do curso, com a ponta redonda
passando pela borda do canal, onde a mola já está dura; o ângulo do flanco quase só muda o
começo do puxão e o quanto a mola fica apertada encaixada (sem folga vertical em J–L). A ponta
mais redonda (L) aperta menos o plástico e segura um pouco menos.

A força vertical que cada barra recebe do canal é a própria força que o plug segura, e o
zigue-zague quase não segura a barra na vertical: as juntas curtas torcem (num modelo de grelha,
5 N moveriam a barra milímetros). Então a barra sempre se apoia no topo ou na base do bolso
enquanto segura, e no O ela empurrava a borda livre deles, na face do plug, o ponto mais fraco.
Mais folga sozinha não resolve, a barra só anda mais até encostar; P e Q escolhem onde ela
encosta: nas pontas, a ~0,35 mm das colunas dos cantos, onde topo e base são rígidos.

Nada de mola impresso no ar: na posição de impressão, lâminas, barra e trechos de mola começam
a 0,2 mm (uma camada) do fundo do bolso, como a lâmina interna do gridv8, ou têm um apoio no
fundo do bolso que para uma camada (`print_layer`) antes deles (lâmina externa do C, mola do
E/F); o apoio se solta na primeira flexão. Nos que imprimem de cabeça para baixo as alturas
são espelhadas para continuar em camadas inteiras. O `mount_plug` padrão continua igual ao A.

## Peças

| peça | quantidade |
|---|---|
| `quadrant_BL`, `quadrant_BR`, `quadrant_FL`, `quadrant_FR` | 1 de cada |
| `spline` (2,0 mm) | 39 (22 na emenda vertical, 17 na horizontal) |
| `mount_plug` | conforme os eletrônicos; é o `mount_plug_P` sem letra (`mount_final` em `params.py`) |
| `test_patch_7` | opcional, para testar o encaixe do plug antes |

## Arquivos

| arquivo | o quê |
|---|---|
| `params.py` | todas as medidas; nomes iguais aos parâmetros do gridv8 |
| `layout.py` | células, quadrantes, emendas, onde vão os plugs de união, contorno e calços |
| `profiles.py` | perfis 2D: canal da parede, chanfros, borda arredondada, ressalto em S, aba da união |
| `grid.py` | anéis das células e os quadrantes |
| `plug.py` | mount plug (o de barra e zigue-zague, e o de duas lâminas do gridv8), cavilha, plug de união, chave de rabo de andorinha, plug duplo |
| `assembly.py` | a peça que junta os quadrantes e onde vai cada uma |
| `configure.py` | muda parâmetros em tempo de execução: roda o `params.py` de novo com outras expressões e recarrega os módulos (o configurador web usa) |
| `spring_model.py` | modelo de vigas das travas do mount plug: força e deformação de cada variante |
| `validate_gridv8.py` | sobrepõe nossos cortes aos do Fusion (`reference/gridv8/`) e mede o desvio |
| `build.py`, `render.py` | exporta para `out/` e gera as prévias |
| `figures.py` | as figuras do README (`docs/`): o mount plug cortado, com as travas em cor |

## Diferenças em relação ao gridv8

O código aplica as regras de forma uniforme. Onde o gridv8 foge delas, a validação lista à parte:

- algumas faces da emenda horizontal (x ≈ −170, −159, −126, −115 e +225) ficaram **sem a folga**
  de 0,075 mm no gridv8 (o Offset Faces não pegou essas faces);
- a lasca de parede no canto interno da borda de trás-direita virou um corpo separado e oculto
  (Body749) no gridv8; aqui ela fica, igual ao lado esquerdo;
- no entalhe da frente, a meia-parede da emenda entre as duas células cortadas foi aparada em
  y=−206,6 no gridv8; aqui ela vai até o entalhe;
- no Sketch13, a face a 60° (lâminas do mount plug, aba do plug de união) está 0,2 mm deslocada
  das outras cinco; aqui as seis faces são iguais;
- um pequeno detalhe na parede interna dos suportes (y≈46,9) não foi reproduzido.

## Ver em 3D

- No Fusion: abrir/inserir os `.step` num design em direct editing.
- No VS Code: extensão **OCP CAD Viewer** (`pip install ocp_vscode`) e `show(objeto)` num script.
