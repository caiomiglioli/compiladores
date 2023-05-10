
# Expressões Regulares Utilizadas para a Identificação dos Tokens Léxicos

**Nome:** Caio Miglioli **RA:** 2135523 

-------------------
## Palavras

| Token   |      RegEx      |  Uso |
|----------|:-------------:|------:|
| ID | ((letra)(letra\|_\|([0-9]))*) | inteiro: **var1** |
| NUM_INTEIRO | \d+ | var1 := **5** |
| NUM_PONTO_FLUTUANTE | \d+[eE][-+]?\d+\|(\\.\d+\|\d+\\.\d*)([eE][-+]?\d+)? | var2 := **5.5** |
| NUM_NOTACAO_CIENTIFICA | (([-\\+]?)([1-9])\\.([0-9])+\[eE\]([-\\+]?)([0-9]+)) | ? |
|||

## Palavras Reservadas

| Token   |      RegEx      |  Uso |
|----------|:-------------:|------:|
| SE |  se | **se** *(expressao) (então)* |
| ENTAO | então | *(se) (expressao)* **então** |
| SENAO | senão | *(se) (corpo)* **senão** *(corpo) (fim)* |
| RETORNA | retorna | **retorna** *(valor)*|
| FIM | fim | *(corpo)* **fim** |
| INTEIRO | inteiro | **inteiro**: (variavel) |
| FLUTUANTE | flutuante | **flutuante**: (variavel) |
| REPITA | repita | **repita** *(corpo) ate* |
| ATE | ate | *repita (corpo)* **ate** |
| LEIA | leia | **leia**() |
| ESCREVA | escreva | **escreva**() |
|||


## Expressões Regulares para Tokens Simples

### Símbolos:
| Token   |      RegEx      |  Uso |
|----------|:-------------:|------:|
|MAIS | \\+ | 1 **+** 1  |
|MENOS | - | 1 **-** 1|
|VEZES | \\* | 1 **\*** 1|
|DIVIDE | / | 1 **/** 1|
|ABRE_PARENTESE | \\( | func **\(** )|
|FECHA_PARENTESE | \\) |func ( **\)** |
|ABRE_COLCHETE | \\[ | variavel **\[** i ]|
|FECHA_COLCHETE | \\] |  variavel [ i **\]**|
|VIRGULA | , | func ( a **,** b )  |
|ATRIBUICAO |:= | a **:=** 1 |
|DOIS_PONTOS | : | inteiro **:** a |
|||

### Operadores Lógicos:
| Token   |      RegEx      |  Uso |
|----------|:-------------:|------:|
|E | && | var **&&** var2 |
|OU | \|\| | var **\|\|** var2 |
|NAO | ! | **!** var |
|||

### Operadores Relacionais:
| Token   |      RegEx      |  Uso |
|----------|:-------------:|------:|
|DIFERENTE  |<> | a **<>** b |'
|MENOR_IGUAL | <= | a **<=** b |
|MAIOR_IGUAL | >= | a **>=** b |
|MENOR | < | a **<** b |
|MAIOR | > | a **>** b |
|IGUAL | = | a **=** b |
|||