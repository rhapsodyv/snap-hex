# Configurador web do SnapHex (site estático)

O gerador roda no navegador, sem servidor que execute código. O site é só um conjunto de arquivos, servido por qualquer
hospedagem de arquivos (GitHub Pages, Cloudflare Pages, Netlify) ou, no Mac, por `python3 -m http.server`. É o mesmo
formato do configurador do [panel holder](https://github.com/rhapsodyv/voron-panel-holder).

- **O motor:** o Python roda no Pyodide (Python compilado para WebAssembly), num Web Worker. O build123d roda sobre o
  [OCP.wasm](https://github.com/yeicor/OCP.wasm), que é o OpenCascade compilado para WebAssembly.
- **O gerador:** os mesmos `.py` de `generator/`, copiados para `web/generator/`. Os parâmetros mudados entram pelo
  `configure.py`, que roda o `params.py` de novo com as novas expressões, então tudo o que deriva deles acompanha.
- **Peças prontas:** com os valores padrão, tudo vem gerado de antemão em `web/pre/`: as malhas da vista, os STLs e o ZIP.
  Assim o site abre na hora, e o motor só é necessário quando um parâmetro muda. O `pre/` não vai no git (são ~90 MB): o
  workflow do Pages gera ele a cada publicação, com o build123d nativo, na mesma versão do motor do navegador.

## Rodar no Mac

```bash
python3 web/package.py
```

```bash
.venv/bin/python web/engine.py pregenerate
```

```bash
python3 -m http.server 8767 --bind 127.0.0.1 --directory web
```

Depois abra `http://127.0.0.1:8767` no Chrome. Refaça os dois primeiros passos sempre que o gerador ou os parâmetros
mudarem: `package.py` copia o gerador, e `pregenerate` refaz as peças prontas (~30 s, quadrantes em paralelo).

## Publicar

O GitHub Pages publica sozinho a cada push na `main` (`.github/workflows/pages.yml`): instala o build123d, roda o
`package.py` e o `pregenerate` e sobe a pasta `web/`. No repositório, o Pages precisa estar com a fonte em
"GitHub Actions" (Settings → Pages). Quem abrir o site consegue ver o código do gerador, porque ele é baixado. O Pyodide
e os pacotes vêm das CDNs públicas (jsDelivr e PyPI), pelos endereços fixos do `pyodide-lock.json`.

## Arquivos

| Arquivo | O que é |
|---|---|
| `index.html`, `style.css`, `app.js` | A página, em inglês: impressora, parâmetros, vista 3D (three.js) e STLs (um por peça ou todos num ZIP). A escolha fica no link, para compartilhar. |
| `fields.js` | Os parâmetros para o usuário (nome, explicação) e os nomes das peças. O resto do `params.py` fica em "Advanced", pelos nomes do gerador e com expressões. |
| `engine.js` | O Web Worker: carrega o Pyodide pela trava, copia o gerador e atende a página. |
| `engine.py` | O lado Python: catálogo (impressoras, parâmetros, peças), uma peça por vez (malha e posições), STL, ZIP, e `pregenerate`. Também roda no Mac, para testar (`.venv/bin/python web/engine.py trident-350 mount_plug`). |
| `pyodide-lock.json` | As versões e os endereços fixos dos pacotes: build123d 0.13.0, OCP.wasm e as dependências (o mesmo do panel holder). |
| `lock.html` | Refaz o `pyodide-lock.json` (para mudar de versão). |
| `package.py` | Copia o gerador para `generator/` e lista os arquivos em `generator/files.json`. |
| `generator/`, `pre/` | Gerados pelos passos acima; não edite à mão. Nenhum dos dois vai no git. |

## Impressoras

Cada impressora é um conjunto de mudanças sobre o `params.py` (que é a Trident 350), em `PRESETS` no `engine.py`. Por
enquanto só a Trident 350 está lá, porque é a única com medidas conferidas na máquina.
