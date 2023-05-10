from sys import argv, exit
import _tppparser

from anytree import RenderTree, AsciiStyle, PreOrderIter
from anytree.exporter import DotExporter, UniqueDotExporter
from _mytree import MyNode

# import re
# import shutil
# import os

def createFunctionsTable(tree):
  funcoes = []

  for node in PreOrderIter(tree):
    # se for declaracao de funcao entao pegar todo o código do cabecalho
    if node.type == 'DECLARACAO_FUNCAO':
      tipo = 'VAZIO'
      c = 0
      if len(node.children) > 1:
        tipo = node.children[0].children[0].children[0].type
        c = 1

      parameters = ''
      for n in PreOrderIter(node.children[c].children[2]): #filho(c) -> filho2 = cabecalho > lista_parametros
        if not n.children and n.name != 'vazio': #se for folha
          parameters += n.name

      params = []
      if parameters:
        parameters = parameters.split(',')
        for p in parameters:
          params.append(p.split(':'))

      util = False
      if node.children[c].children[0].children[0].name == 'principal':
        util = True

      funcoes.append({
        'tipo': tipo,
        'nome': node.children[c].children[0].children[0].name,
        'parametros': params,
        'linhaInicial': node.children[c].children[0].lineno,
        'linhaFinal': node.children[c].children[5].lineno,
        'utilizado': util,
        'node': node,
      })
  return funcoes
#end createFunctionsTable


def createVariablesTable(tree, functions):
  vars = []

  for node in PreOrderIter(tree):
    if node.type == 'DECLARACAO_VARIAVEIS':
      tipo = node.children[0].children[0].children[0].type
      linha = node.children[0].children[0].children[0].lineno

      varAux = ''
      for n in PreOrderIter(node.children[2]): #filho 2 = lista variaveis
        if not n.children: #se for folha
          varAux += n.name

      varAux = varAux.split(',')
      for var in varAux:
        v = var.replace(']', '').split('[')

        vars.append({
          'tipo': tipo,
          'nome': v[0],
          'dimensoes': v[1:], #converte todos os items em int a partir do indice 1 até o final
          'linha': linha,
          'escopo': getScope(linha, functions),
          'init': False,
          'utilizado': False,
          'node': node,
        })
      #end for
    #end declaracao variaveis

    if node.type == 'PARAMETRO' and node.children[0].type != 'PARAMETRO':
      linha = node.children[0].children[0].lineno

      dimensoes = []
      n = node.parent
      while(n.type == 'PARAMETRO'):
        dimensoes.append('P')
        n = n.parent

      vars.append({
        'tipo': node.children[0].children[0].type,
        'nome': node.children[2].children[0].name,
        'dimensoes': dimensoes,
        'linha': linha,
        'escopo': getScope(linha, functions),
        'init': linha,
        'utilizado': False,
        'node': node,
      })
    #end parametros
  #end for
  return vars
#end create var table

#########################################
#########################################
#########################################
#regras

#regra 1 --- wtf

#regra 2
def r2_funcPrincipal(func, var):
  found = []
  for f in func:
    if f['nome'] == 'principal':
      found.append(f)
  
  if len(found) < 1:
    return 'ERRO: Função principal não declarada.'
  elif len(found) > 1:
    return 'ERRO: Função principal declarada mais de uma vez.'

  if found[0]['tipo'] != 'INTEIRO':
    return 'ERRO: Função principal deve ser do tipo inteiro.'
  
  #retorno
  return verifyFuncReturn(func, var, found[0])
#end regra2


#regra 3
def r3_paramsQtde(tree, func, var):
  for node in PreOrderIter(tree):
    if node.type == 'CHAMADA_FUNCAO':
      #PEGAR O NOME DA FUNCAO
      nomeFunc = node.children[0].children[0].name
      linhaFunc = node.children[0].children[0].lineno

      #PEGAR A QUANTIDADE DE VARIAVEIS, POSSIVELMENTE O TIPO?
      listaArgumentos = node.children[2]
      paramsQtde = 0
      while listaArgumentos.type == 'LISTA_ARGUMENTOS' and listaArgumentos.children[0].type != 'VAZIO':
        paramsQtde += 1
        listaArgumentos = listaArgumentos.children[0]
      
      #logica
      for f in func:
        if f['nome'] == nomeFunc and len(f['parametros']) != paramsQtde:
          return 'ERRO: Chamada à função \'' + nomeFunc + '\' (linha ' + str(linhaFunc) + ') com número de parâmetros diferente que o declarado.'
#end regra3


#regra 4
def r4_chamadaDeFuncao(tree, func, var):
  #retorno compativel - Erro: Função principal deveria retornar inteiro, mas retorna vazio.
  for f in func:
    if f['nome'] != 'principal':
      r = verifyFuncReturn(func, var, f)
      if r:
        return r, func

  #Erro: Chamada a função ‘func’ que não foi declarada.
  for node in PreOrderIter(tree):
    if node.type == 'CHAMADA_FUNCAO':
      #PEGAR O NOME DA FUNCAO
      nomeChamada = node.children[0].children[0].name
      linhaChamada = node.children[0].children[0].lineno

      #Erro: Chamada para a função principal não permitida.
      if nomeChamada == 'principal':
        if getScope(linhaChamada, func) != 'principal':
          res = 'ERRO: Chamada para a função principal não permitida.'
          return res, func
        else:
          print('AVISO: Chamada recursiva para principal.')
      #endif

      notFound = True
      for f in func:
        if f['nome'] == nomeChamada and f['linhaInicial'] <= linhaChamada: #está ok
          f['utilizado'] = True #atualizar o functions
          notFound = False
          break
      
      if notFound:
        res = 'ERRO: Chamada a função \'' + nomeChamada + '\' (linha ' + str(linhaChamada) + ') que não foi declarada.'
        return res, func
    #end if
  #end for

  #Aviso: Função ‘func’ declarada, mas não utilizada.
  for f in func:
    if f['utilizado'] == False:
      print('AVISO: Função \'' + f['nome'] + '\' declarada, mas não utilizada.')
  return None, func
#end regra 4    
      

#regra5
def r5_variaveis(tree, func, var):
  # Aviso: Variável ‘a’ já declarada anteriormente
  varlist = []
  for v in var:
    aux = [v['nome'], v['escopo']]
    if aux not in varlist:
      varlist.append(aux)
    else:
      return 'ERRO: Variável \'{}\' (linha {}) já declarada anteriormente.'.format(v['nome'],v['linha']), var

  for node in PreOrderIter(tree):
    if node.type == 'VAR' and node.parent.type != 'LISTA_VARIAVEIS': #se for um var, mas nao ser filho de um lista variaveis (nao faz parte de uma declaracao de var)
      varName = node.children[0].children[0].name
      varLine = node.children[0].children[0].lineno
      varScope = getScope(varLine, func)

      # Erro: Variável ‘a’ não declarada.
      if [varName, varScope] not in varlist:
        if [varName, 'global'] not in varlist:
          res = 'ERRO: Variável \'' + varName + '\' (linha ' + str(varLine) + ') não declarada.'
          return res, var

      # Aviso: Variável ‘a’ declarada e não inicializada.
      #if nodetype != de atribuicao

    #FAZER A REGRA 6 PRIMEIRO AAAAAAAAAAAA
    #FAZER A REGRA 6 PRIMEIRO AAAAAAAAAAAA
    #FAZER A REGRA 6 PRIMEIRO AAAAAAAAAAAA
    #FAZER A REGRA 6 PRIMEIRO AAAAAAAAAAAA

  # Aviso: Variável ‘a’ declarada e não utilizada.
  return None, var
#end regra5


#regra6
def r6_atribuicao(tree, func, var):
  for node in PreOrderIter(tree):
    if node.type == 'ATRIBUICAO' and node.parent.type != 'ATRIBUICAO':
      #"""atribuicao : var ATRIBUICAO expressao"""
      varName = node.children[0].children[0].children[0].name
      varLine = node.children[0].children[0].children[0].lineno
      varScope = getScope(varLine, func)
      varTipo = None

      #atualizar info da tabela de var e pegar o vartipo
      #utilizado = true, init = varline
      gg = None
      vv = None
      for v in var:
        if v['nome'] == varName and v['escopo'] == varScope: #variavel com o escopo da funcao
          varTipo = v['tipo']
          v['utilizado'] = True
          if v['init'] == False or v['init'] > varLine:
            v['init'] = varLine

      #caso o varTipo nao tenha sido alterado na checagem anterior, é pq nao tem variavel local com aquele nome
      if not varTipo: 
        for v in var:
          if v['nome'] == varName and v['escopo'] == 'global': #variavel com o escopo da funcao
            varTipo = v['tipo']
            v['utilizado'] = True
            if v['init'] == False or v['init'] > varLine:
              v['init'] = varLine

      if varTipo:
        #Aviso: Atribuição de tipos distintos ‘a’ inteiro e ‘expressão’ flutuante
        expType = verifyExpressionType(node.children[2], func, var, escopo=varScope)
        if varTipo != expType:
          print('AVISO (Coerção implícita): Atribuição de tipos distintos \'{}\' ({}) e resultado da expressão ({}) (linha {}).'.format(varName, varTipo.lower(), expType.lower(), varLine))
      else:
        return 'ERRO: Inesperado na linha {}.'.format(varLine), var

    #fazer com que o X de leia(x) seja inicializado na tabela
    if node.type == 'VAR' and node.parent.type == 'LEIA':
      varName = node.children[0].children[0].name
      varLine = node.children[0].children[0].lineno
      varScope = getScope(varLine, func)

      init = False
      for v in var:
        if v['nome'] == varName and v['escopo'] == varScope: #variavel com o escopo da funcao
          v['utilizado'] = True
          init = True
          if v['init'] == False or v['init'] > varLine:
            v['init'] = varLine
      if not init:
        for v in var:
          if v['nome'] == varName and v['escopo'] == 'global': #variavel com o escopo global
            v['utilizado'] = True
            if v['init'] == False or v['init'] > varLine:
              v['init'] = varLine
    #end if
  #end for
  return None, var
#end regra6


#regra5 continuacao desnecessario mais....
def r5_variaveis_continuacao(tree, func, var):
  for node in PreOrderIter(tree):
    # Aviso: Variável ‘a’ declarada e não inicializada.
    if node.type == 'VAR' and node.parent.type == 'FATOR':
      varName = node.children[0].children[0].name
      varLine = node.children[0].children[0].lineno
      varScope = getScope(varLine, func)

      vAux = None
      for v in var:
        if v['nome'] == varName and v['escopo'] == varScope:
          v['utilizado'] = True
          vAux = v
      if not vAux:
        for v in var:
          if v['nome'] == varName and v['escopo'] == 'global':
            v['utilizado'] = True
            vAux = v

      if vAux:
        if varLine <= vAux['init'] or not vAux['init']:
          print('AVISO: Leitura da variável \'{}\' declarada mas não inicializada (Linha {}).'.format(varName,varLine))
      else:
        return 'ERRO: Inesperado na linha {}.'.format(varLine), var
  #end for

  # Aviso: Variável ‘a’ declarada e não utilizada.
  for v in var:
    if not v['utilizado']:
      print('AVISO: Variável \'{}\' declarada e não utilizada (Linha {}).'.format(v['nome'], v['linha']))

  return None, var
#end regra5 continuacao

#regra 7 -- mesma coisa do 6????
#end regra7

#regra 8
def r8_arranjos(tree, func, var):
  for node in PreOrderIter(tree):
    #Erro: Índice de array ‘X’ não inteiro.
    if node.type == 'INDICE':
      exp = node.children[1]
      line = node.children[-1].children[0].lineno
      scope = getScope(line, func)

      c = node.children[1]
      if node.children[0].type == 'INDICE':
        c = node.children[2]

      if verifyExpressionType(c, func, var, scope) != 'INTEIRO':
        return 'ERRO: Array com índice não inteiro (Linha {}).'.format(line)
          
      
      # Erro: índice de array ‘A’ fora do intervalo (out of range)
      if node.parent.type == 'VAR' and node.parent.parent.type != 'LISTA_VARIAVEIS': #Se for indice mas nao for em declaracao
        varName = node.parent.children[0].children[0].name
        varLine = node.parent.children[0].children[0].lineno
        varScope = getScope(varLine, func)
        
        vv = None
        for v in var:
          if v['nome'] == varName and v['escopo'] == varScope:
            vv = v
        if not vv:
          for v in var:
            if v['nome'] == varName and v['escopo'] == 'global':
              vv = v

        if vv:
          dimensoes = [x for x in vv['dimensoes']]
          n = node
          while(n.type == 'INDICE'):
            if not dimensoes:
              return 'ERRO: Há mais dimensões que o declarado para a variável \'{}\' (Linha {}).'.format(varName, varLine)
            dim = dimensoes.pop(-1)
            indexValue = getExpressionValue(func, var, n.children[-2])
            if indexValue != 'VAR' and int(dim) <= indexValue:
              return 'ERRO: índice de array \'{}\' (Linha {}) fora do intervalo declarado (out of range).'.format(varName,varLine)
            n = n.children[0]
        else:
          return 'ERRO: Inesperado na linha {}.'.format(varLine)
  return None
#end regra 8

#########################################
#########################################
#########################################

def getExpressionValue(func, var, node):
  texto = ''
  
  for n in PreOrderIter(node):
    if n.type == 'VAR' or n.type == 'CHAMADA_FUNCAO':
      return 'VAR'

    if not n.children:
      texto += n.name

  return eval(texto)
#end getexpressionvalue

def verifyFuncReturn(func, var, f):
  node = f['node']

  if f['tipo'] == 'VAZIO':
    for child in PreOrderIter(node):
      if child.type == 'RETORNA':
        return 'ERRO: A função \'{}\' declarada como VAZIO não pode retornar um valor.'.format(f['nome'])
    return None

  returnFlag = False
  for child in PreOrderIter(node):
    if child.type == 'RETORNA' and child.parent.type != 'RETORNA':
      # if child.children: #somente os nodes que tenham filhos (nao vai entrar no folha)
      returnFlag = True
      if verifyExpressionType(node=child.children[2], func=func, var=var, escopo=f['nome']) != f['tipo']:
        return 'ERRO: Função \'' + f['nome'] + '\' deve retornar um item do tipo \'' + f['tipo'] + '\'.'
  
  if not returnFlag:
    return 'ERRO: Função \'' + f['nome'] + '\' deveria retornar \'' + f['tipo'] + '\', mas retorna vazio.'
#END _FUNCRETORNO


def verifyExpressionType(node, func, var, escopo='global'):
  t = 'VAZIO'
  for n in PreOrderIter(node, stop=lambda n: n.type == 'LISTA_ARGUMENTOS'):
    tipo = n.type
    #check var
    if tipo == 'VAR':
      for v in var:
        if v['nome'] == n.children[0].children[0].name and v['escopo'] == escopo:
          tipo = v['tipo']
          break
        elif v['nome'] == n.children[0].children[0].name and v['escopo'] == 'global': #escopo da funcao tem precedencia sobre o global, por isso elif
          tipo = v['tipo']
          break

    #check func
    if tipo == 'CHAMADA_FUNCAO':
      for f in func:
        if f['nome'] == n.children[0].children[0].name:
          tipo = f['tipo']
          # print(f['nome'], f['tipo'], n.children[0].children[0].name)
          break

    #check num
    if (tipo == 'NUM_INTEIRO' or tipo == 'INTEIRO') and t == 'VAZIO':
      t = 'INTEIRO'
    if (tipo == 'NUM_PONTO_FLUTUANTE' or tipo == 'FLUTUANTE') and t != 'NUM_NOTACAO_CIENTIFICA':
      t = 'FLUTUANTE'
    if tipo == 'NUM_NOTACAO_CIENTIFICA' or tipo == 'NOTACAO_CIENTIFICA':
      t = 'NOTACAO_CIENTIFICA'

  return t
#end verifyExpressionType


def getScope(line, table):
  for row in table:
    if row['linhaInicial'] <= line and row['linhaFinal'] >= line:
      return row['nome']
  return 'global'
#end 

#########################################
#########################################
#########################################
#podar arvore

def podarArvore(tree):
  #PODAR ATRIBUICAO
  for node in PreOrderIter(tree):
    if node.type == 'ATRIBUICAO' and node.name == 'atribuicao':
      atrPai = node.parent
      atrSimbolo = node.children[1].children[0]
      atrVariavel = node.children[0].children[0].children[0]
      atrExpressao = node.children[2]

      #pai
      for c in atrPai.children:
        if c == node:
          c.parent = None
          c = atrSimbolo
          break
      
      #simbolo
      atrSimbolo.parent = atrPai
      atrSimbolo.children = (atrVariavel, atrExpressao)

      #var
      atrVariavel.type = 'VAR'
      atrVariavel.parent = atrSimbolo

      #exp
      atrExpressao.parent = atrSimbolo
      
  ##############################################
  #PODAR EXPRESSOES ARITMETICAS
  cabacagemFlag = True
  while(cabacagemFlag):
    cabacagemFlag = False
    for node in PreOrderIter(tree):
      if node.type in ['EXPRESSAO_ADITIVA','EXPRESSAO_MULTIPLICATIVA','EXPRESSAO_SIMPLES', 'EXPRESSAO_LOGICA']:
        if len(node.children) != 3:
          continue

        # print(node.info, len(node.children))
        exp1 = node.children[0]
        exp2 = node.children[2]
        simbolo = node.children[1].children[0].children[0]

        #simbolo
        exp1.parent = simbolo
        exp2.parent = simbolo
        simbolo.children = (exp1, exp2)
        simbolo.parent = node.parent

        #node parent
        for n in node.parent.children:
          if n == node:
            n = simbolo

        node.parent = None
        cabacagemFlag = True
        break
      #endif
    #endffor
  #endwhile
  
  ##############################################
  #REMOVE O NÓ E TODOS SEUS FILHOS
  remAux = ['ABRE_PARENTESE','FECHA_PARENTESE','FIM','DOIS_PONTOS', 'VIRGULA', 'ABRE_COLCHETE', 'FECHA_COLCHETE']
  for node in PreOrderIter(tree):
    remove = False

    if node.type in remAux:
      remove = True
    elif node.name == 'corpo' and node.children[0].name == 'vazio':
      remove = True
    elif node.name in ['ESCREVA', 'RETORNA', 'LEIA', 'SE', 'ENTAO', 'SENAO', 'ATE', 'REPITA']:
      remove = True

    if remove:
      node.parent.children = (c for c in node.parent.children if node != c)
      node.parent = None

  ##############################################
  #REMOVE UM NÓ SEM TIRAR OS FILHOS DA ARVORE
  remAux = ['VALOR', 'ID', 'INTEIRO', 'FLUTUANTE', 'SIMBOLO', 'VAR', 'CHAMADA_FUNCAO', 'EXPRESSAO_UNARIA'] #'ACAO', 'DECLARACAO'
  goodParents = ['escreva', 'leia', 'retorna', 'corpo']
  cabacagemFlag = True
  while(cabacagemFlag):
    cabacagemFlag = False
    for node in PreOrderIter(tree):
      if (node.type in remAux) and len(node.parent.children) == 1 and node.parent.name not in goodParents:
        pai = node.parent
        vo = node.parent.parent

        aux = []
        for n in vo.children:
          if n == pai:
            aux.append(node)
          else:
            aux.append(n)
        vo.children = (x for x in aux)

        pai.parent = None
        node.parent = vo    

        cabacagemFlag = True
        break
         

  return tree
#end podararvore

#########################################
#########################################
#########################################

def main(file):
    if file:
        argv[1] = file

    aux = argv[1].split('.')
    if aux[-1] != 'tpp':
      raise IOError("Not a .tpp file!")

    tree = _tppparser.main(argv[1])
    # print(RenderTree(root, style=AsciiStyle()).by_attr())

    if tree:
      #tabelas
      functions = createFunctionsTable(tree)
      variables = createVariablesTable(tree, functions)

      #regras
      r2 = r2_funcPrincipal(functions, variables)
      r3 = r3_paramsQtde(tree=tree, func=functions, var=variables)
      r4, functions = r4_chamadaDeFuncao(tree=tree, func=functions, var=variables)
      r5, variables = r5_variaveis(tree=tree, func=functions, var=variables)
      r6, variables = r6_atribuicao(tree=tree, func=functions, var=variables)
      r5c, variables = r5_variaveis_continuacao(tree=tree, func=functions, var=variables)
      r8 = r8_arranjos(tree=tree, func=functions, var=variables)
      #regras extras
      
      error = False
      for e in [r2, r3, r4, r5, r6, r5c, r8]:
        if e:
          print(e)
          error = True
      
      if error:
        print('Não foi possível continuar a compilação: A análise semântica falhou...')
        return None

      p = podarArvore(tree)
      UniqueDotExporter(p).to_picture(argv[1] + ".unique.ast.poda.png")
      
      # ##############################
      # ## print tabelas atualizadas:
      # print('\n\nfuncs:')
      # for f in functions:
      #   print(f)

      # print('vars:')
      # for i in variables:
      #   print(i)
      
      return tree, functions, variables
#end main()

if __name__ == "__main__":
    main()