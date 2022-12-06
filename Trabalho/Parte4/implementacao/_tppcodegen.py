from sys import argv, exit
import re
import _tppsemantica

from anytree import RenderTree, AsciiStyle, PreOrderIter
from anytree.exporter import DotExporter, UniqueDotExporter
from _mytree import MyNode

from llvmlite import ir
from llvmlite import binding as llvm

#########################################
#########################################
#########################################

class CodeGen():
    def __init__(self, tree, func, var, **kwargs):
        self.tree = tree
        self.escopo = 'global'
        self.funcoes = func
        self.variaveis = var
        self.builder = None
        self.builderExitBlock = None

        llvm.initialize()
        llvm.initialize_all_targets()
        llvm.initialize_native_target()
        llvm.initialize_native_asmprinter()

        self.module = ir.Module('module.bc')
        self.module.triple = llvm.get_default_triple()
        target = llvm.Target.from_triple(self.module.triple)
        target_machine = target.create_target_machine()
        self.module.data_layout = target_machine.target_data

        self.escrevaInteiro = ir.Function(self.module,ir.FunctionType(ir.VoidType(), [ir.IntType(32)]),name="escrevaInteiro")
        self.escrevaFlutuante = ir.Function(self.module,ir.FunctionType(ir.VoidType(),[ir.FloatType()]),name="escrevaFlutuante")
        self.leiaInteiro = ir.Function(self.module,ir.FunctionType(ir.IntType(32),[]),name="leiaInteiro")
        self.leiaFlutuante = ir.Function(self.module,ir.FunctionType(ir.FloatType(),[]),name="leiaFlutuante")
    #end init

    #$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
    #$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
    # HELPERS

    def getVar(self, varName):
        var = None
        for v in self.variaveis:
            if v['nome'] == varName:
                if v['escopo'] == self.escopo or (v['escopo'] == 'global' and var == None):
                    var = v
        return var
    #end getvar
    
    def getFunc(self, funcName):
        for f in self.funcoes:
            if f['nome'] == funcName:
                return f
    #end getvar

    def getExpressionLlvm(self, node):
        ret = None
        if node.type == 'VALOR':
            if re.search('\.', node.name) != None: #é flutuante
                ret = ir.Constant(ir.FloatType(), float(node.name))
            else:
                ret = ir.Constant(ir.IntType(32), int(node.name))
        
        elif node.type == 'ID':
            var = self.getVar(node.name)
            ret = self.builder.load(var['llvmVar'])
        
        elif node.type == 'CHAMADA_FUNCAO':
            ret = self.callFunc(node)
        
        elif node.type == 'SIMBOLO':
            ret = self.expAritmetica(node)

        elif node.type == 'EXPRESSAO_UNARIA':
            valor = self.getConditionalLlvm(node.children[1])
            vTipo = ir.FloatType() if re.search('float', str(valor)) else ir.IntType(32)

            if node.children[0].name == '+':
                ret = valor
            elif node.children[0].name == '-':
                ret = self.builder.sub(ir.Constant(vTipo, 0), valor, name='subUnario$')
            elif node.children[0].name == '!':
                ret = self.builder.icmp_signed('==', valor, ir.Constant(vTipo, 0), name='notUnario$') # se valor == 0 entao retorna 1, se valor == (qq coisa) entao retorna 0

        return ret
    #end getexprerssionllvm

    def expAritmetica(self, node):
        esquerda = node.children[0]
        direita = node.children[1]

        llvmEsq = self.getExpressionLlvm(esquerda)
        llvmDir = self.getExpressionLlvm(direita)

        #coerção xd
        e = re.search('float', str(llvmEsq))
        d = re.search('float', str(llvmDir))
        if e and not d:
            llvmDir = self.builder.sitofp(llvmDir, ir.FloatType(), name="llvmDir$")
        elif not e and d:
            llvmEsq = self.builder.sitofp(llvmEsq, ir.FloatType(), name="llvmEsq$")

        if(node.name == "+"): return self.builder.add(llvmEsq, llvmDir, name='sum$')
        elif(node.name == "-"): return self.builder.sub(llvmEsq, llvmDir, name='sub$')
        elif(node.name == "*"): return self.builder.mul(llvmEsq, llvmDir, name='mult$')
        elif(node.name == "/"): return self.builder.sdiv(llvmEsq, llvmDir, name='div$')
        else: raise Exception("ERRO: Não foi possível gerar código de Expressão Aritmetica.")
    #end expAritmetica

    def verifyExpressionType(self, node):
        for n in PreOrderIter(node, stop=lambda n: n.parent.type == 'CHAMADA_FUNCAO'):
            if n.type == 'CHAMADA_FUNCAO':
                func = self.getFunc(n.children[0].name)
                if func['tipo'] == 'FLUTUANTE': #chamadafunc
                    return 'FLUTUANTE'
                # continue

            elif n.type == 'ID':
                var = self.getVar(n.name)
                if var['tipo'] == 'FLUTUANTE': #id
                    return 'FLUTUANTE'
            
            elif n.type == 'VALOR':
                if re.search('\.', n.name) != None: #é flutuante
                    return 'FLUTUANTE'
            
        return 'INTEIRO'
    #end verifyExpressionType

    def getConditionalLlvm(self, node):
        if node.name in ['&&', '||', '<>', '=', '>', '<', '>=', '<=']:
            return self.condicional(node)
        else:
            return self.getExpressionLlvm(node)
    #end getconditionalllvm

    def condicional(self, node):
        if node.type in ['EXPRESSAO_UNARIA', 'ID', 'CHAMADA_FUNCAO', 'VALOR']:
            return self.getExpressionLlvm(node)

        esquerda = node.children[0]
        direita = node.children[1]

        llvmEsq = self.getConditionalLlvm(esquerda)
        llvmDir = self.getConditionalLlvm(direita)
        
        if node.name == '&&':
            return self.builder.and_(llvmEsq, llvmDir, name='and$')
        elif node.name == '||':
            return self.builder.or_(llvmEsq, llvmDir, name='or$')
        elif node.name == '<>':
            return self.builder.icmp_signed('!=', llvmEsq, llvmDir, name='diferente$')
        elif node.name == '=':
            return self.builder.icmp_signed('==', llvmEsq, llvmDir, name='igual$')
        elif node.name == '>':
            return self.builder.icmp_signed('>', llvmEsq, llvmDir, name='maior$')
        elif node.name == '<':
            return self.builder.icmp_signed('<', llvmEsq, llvmDir, name='menor$')
        elif node.name == '>=':
            return self.builder.icmp_signed('>=', llvmEsq, llvmDir, name='maiorIgual$')
        elif node.name == '<=':
            return self.builder.icmp_signed('<=', llvmEsq, llvmDir, name='menorIgual$')
    #end condicional

    # HELPERS
    #$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
    #$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
    # CODEGENERATORS

    def declVariaveis(self, node):
        #LLVM code -- pra n repetir
        def _declGlobal(module, type, name, value):
            v = ir.GlobalVariable(module, type, name=name)
            v.initializer = ir.Constant(type, value)
            v.linkage = "common"
            v.align = 4

            var = self.getVar(name)
            var['llvmVar'] = v
            
        def _declLocal(module, type, name, value):
            v = self.builder.alloca(type, name=name)
            v.align = 4

            var = self.getVar(name)
            var['llvmVar'] = v
        #end llvmcode

        if node.children[0].name == 'inteiro':
            type = ir.IntType(32)
            initValue = 0
        else:
            type = ir.FloatType()
            initValue = 0.0
                
        #se tiver var, eh pq tem indice
        if node.children[-1].type == 'VAR':
            print('FAZER DECL DE ARRAY EM ALGUM MOMENTO')
            raise Exception("ARRAY")

        #se tiver lista_variaveis, eh pq sao varias
        elif node.children[-1].type == 'LISTA_VARIAVEIS':
            for n in PreOrderIter(node.children[-1]):
                if not n.children:
                    if self.escopo == 'global':
                        _declGlobal(self.module, type, n.name, initValue)
                    else:
                        _declLocal(self.module, type, n.name, initValue)

        #se tiver o nome direto, eh pq é simples
        else:
            if self.escopo == 'global':
                _declGlobal(self.module, type, node.children[-1].name, initValue)
            else:
                _declLocal(self.module, type, node.children[-1].name, initValue)
    #end declVariaveis

    def declFuncao(self, node):        
        f = self.getFunc(node.children[-1].children[0].name)
        self.escopo = f['nome']

        #auxiliar
        ft = ir.IntType(32) if f['tipo'] == 'INTEIRO' else ir.FloatType() # ternario para decidir o tipo de retorno da funcao
        args = [ir.IntType(32) if x[0] == 'inteiro' else ir.FloatType() for x in f['parametros']] # tupla contendo um ternario para cada elemento do array f['parametros']
        funcName = 'main' if f['nome'] == 'principal' else f['nome']
        
        #cabecalho da funcao
        funcType = ir.FunctionType(ft, args) # nessa linha é declrado o tipo de retorno e os argumentos da função FunctionType(type, (list of type))
        function = ir.Function(self.module, funcType, funcName)
        f['llvmFunction'] = function

        # Cria o corpo da função
        entryBlock = function.append_basic_block('entry')
        self.builder = ir.IRBuilder(entryBlock)
        endBasicBlock = function.append_basic_block('exit')
        self.builderExitBlock = endBasicBlock

        #parametros
        for i, arg in enumerate(function.args):
            argName = f['parametros'][i][1]
            arg.name = 'p_' + argName #coloca o nome do arg a partir dos parametros declarados
            
            #crio uma variavel local e insiro o conteudo do parametro
            argLlvm = self.builder.alloca(args[i], name=argName)
            self.builder.store(arg, argLlvm)
            
            #ponteiros
            f['parametros'][i].append(argLlvm) #coloca o llvm do arg na tabela de funcoes
            v = self.getVar(argName)
            v['llvmVar'] = argLlvm  #coloca o llvm do arg na tabela de variaveis
        #end for

        # Variavel de retorno
        r = self.builder.alloca(ft, name='retorna$') # Declarando e alocando a variavel 'retorno'
        r.align = 4
        #self.builder.store(ir.Constant(ft, 0) , r)
        f['llvmReturn'] = r #criando "ponteiro" para utilizar essa variavel em outro local

        #agr é codigo do corpo da funcao
        self.navigate(node.children[-1].children[-1])

        # final da funcao (coloca o branch só se nao tiver um return)
        try:
            self.builder.branch(endBasicBlock) #bugando
        except:
            pass
        
        #return
        self.builder.position_at_end(endBasicBlock)
        if f['tipo'] == 'VAZIO':
            self.builder.ret_void()
        else:
            returnVal_temp = self.builder.load(r, name='ret_temp$', align=4)
            self.builder.ret(returnVal_temp)

        self.escopo = 'global'
    #end declFuncao


    def atribuicao(self, node):
        var = self.getVar(node.children[0].name)
        llvmVar = var['llvmVar']
        exp = node.children[1]
        temp1 = None
        
        #exp pode ser aritmetica (+ - * /) >> type = SIMBOLO
        if exp.type == 'SIMBOLO':
            temp1 = self.expAritmetica(exp)

        #exp pode ser chamada de funcao >> type = CHAMADA_FUNCAO
        elif exp.type == 'CHAMADA_FUNCAO':
            temp1 = self.callFunc(exp)

        #exp pode ser valor unico >> type = VALOR
        elif exp.type in ['VALOR', 'EXPRESSAO_UNARIA']:
            temp1 = self.getExpressionLlvm(exp)

        #exp pode ser variavel >> type = ID
        elif exp.type == 'ID':
            expVar = self.getVar(exp.name)
            expLlvmVar = expVar['llvmVar']
            temp1 = self.builder.load(expLlvmVar, name="temp1$")

        #coercao
        t = re.search('float', str(temp1))
        if var['tipo'] == 'FLUTUANTE' and not t: #t = inteiro 
            temp1 = self.builder.sitofp(temp1, ir.FloatType(), name="temp1$") # temp1 = (float) temp1
            
        elif var['tipo'] == 'INTEIRO' and t: #t = float
            temp1 = self.builder.fptosi(temp1, ir.IntType(32), name="temp1$") # temp1 = (int) temp1
               
        self.builder.store(temp1, llvmVar)
        #end var
    #end atribuicao

    def callFunc(self, node):
        func = self.getFunc(node.children[0].name)
        if not func:
            raise Exception("ERRO: Não foi possível gerar código de chamada de função.")

        params = []
        #rodar em preordem eu consigo os parametros em ordem e folha.nome != vazio
        for n in PreOrderIter(node.children[1], stop=lambda n: (n.parent != node and n.parent.type in ['CHAMADA_FUNCAO', 'SIMBOLO'])): #nao descer quando o pai for um 'chamada funcao' (exceto o root)
            if n.type == 'VALOR':
                if re.search('\.', n.name) != None: #é flutuante
                    params.append(ir.Constant(ir.FloatType(), float(n.name)))
                else:
                    params.append(ir.Constant(ir.IntType(32), int(n.name)))

            elif n.type == 'ID':
                var = self.getVar(n.name)
                params.append(self.builder.load(var['llvmVar']))

            elif n.type == 'CHAMADA_FUNCAO':
                chFunc = self.callFunc(n) #recursivo para resolver uma funcao dentro da outra :DDDD
                params.append(chFunc)

            elif n.type == 'SIMBOLO':
                exp = self.getExpressionLlvm(n)
                params.append(exp)
        #end for
        return self.builder.call(func["llvmFunction"], params)
    #end callfunc


    def retorna(self, node):
        f = self.getFunc(self.escopo)
        fTipo = ir.IntType(32) if f['tipo'] == 'INTEIRO' else ir.FloatType() # ternario para decidir o tipo de retorno da funcao
        exp = node.children[0]

        try:
            #valor
            if exp.type == 'VALOR':
                value = int(exp.name) if f['tipo'] == 'INTEIRO' else float(exp.name)
                self.builder.store(ir.Constant(fTipo, value), f['llvmReturn'])

            #chamada_funcao
            elif exp.type == 'CHAMADA_FUNCAO':
                temp1 = self.callFunc(exp)
                self.builder.store(temp1, f['llvmReturn'])

            #simbolo
            elif exp.type == 'SIMBOLO':
                temp1 = self.expAritmetica(exp)
                self.builder.store(temp1, f['llvmReturn'])
            #ID
            elif exp.type == 'ID':
                expVar = self.getVar(exp.name)
                expLlvmVar = expVar['llvmVar']
                temp1 = self.builder.load(expLlvmVar, name="retorna_var$")

                #coercao
                if f['tipo'] == 'FLUTUANTE' and expVar['tipo'] == 'INTEIRO':
                    temp1 = self.builder.sitofp(temp1, ir.FloatType(), name="retorna_var$") # temp1 = (float) temp1
                elif f['tipo'] == 'INTEIRO' and expVar['tipo'] == 'FLUTUANTE':
                    temp1 = self.builder.fptosi(temp1, ir.IntType(32), name="retorna_var$") # temp1 = (int) temp1

                self.builder.store(temp1, f['llvmReturn'])

            #faz pular pro exit
            self.builder.branch(self.builderExitBlock) #bugando
        except:
            print("AVISO: Há mais de um retorna() no mesmo escopo.")
    #end retorna(node)

    def leia(self, node):
        var = self.getVar(node.children[0].name)
        tempLeia = None

        if var['tipo'] == 'INTEIRO':
            tempLeia = self.builder.call(self.leiaInteiro, [])
        else:
            tempLeia = self.builder.call(self.leiaFlutuante, [])

        self.builder.store(tempLeia, var['llvmVar'])
    #end leia

    def escreva(self, node):
        exp = node.children[0]
        expType = self.verifyExpressionType(exp)
        func2call = self.escrevaInteiro if expType == 'INTEIRO' else self.escrevaFlutuante
        params = []

        #exp pode ser aritmetica (+ - * /) >> type = SIMBOLO
        if exp.type == 'SIMBOLO':
            temp1 = self.expAritmetica(exp)
            params.append(temp1)

        #exp pode ser chamada de funcao >> type = CHAMADA_FUNCAO
        elif exp.type == 'CHAMADA_FUNCAO':
            chFunc = self.callFunc(exp) #recursivo para resolver uma funcao dentro da outra :DDDD
            params.append(chFunc)

        #exp pode ser valor unico >> type = VALOR
        elif exp.type == 'VALOR':
            if re.search('\.', exp.name) != None: #é flutuante
                params.append(ir.Constant(ir.FloatType(), float(exp.name)))
            else:
                params.append(ir.Constant(ir.IntType(32), int(exp.name)))

        #exp pode ser variavel >> type = ID
        elif exp.type == 'ID':
                var = self.getVar(exp.name)
                params.append(self.builder.load(var['llvmVar']))

        return self.builder.call(func2call, params)
    #end escreva

    def seEntao(self, node):
        # if len(children.n)
        f = self.getFunc(self.escopo)
        if_block = f['llvmFunction'].append_basic_block(name="if")
        self.builder.branch(if_block)
        self.builder.position_at_end(if_block)

        #resolver condicional:
        cond = self.condicional(node.children[0])

        if len(node.children) > 2:
            with self.builder.if_else(cond) as (then, otherwise):
                with then:
                    self.navigate(node.children[1])
                with otherwise:
                    self.navigate(node.children[2])
        else:
            with self.builder.if_then(cond):
                self.navigate(node.children[1])
    #end seentao

    def repita(self, node):
        #add bloco do loop
        f = self.getFunc(self.escopo)
        loop_block = f['llvmFunction'].append_basic_block(name="loop")
        self.builder.branch(loop_block)
        self.builder.position_at_end(loop_block)

        #add corpo do loop
        self.navigate(node.children[0])

        #condicional do loop
        cond = self.condicional(node.children[1])
        cond = self.builder.not_(cond, name='Loop_Condicional$') #gambiarra pois o ifthen vai executar o branch quando True, mas o repitaAté executa quando False

        #checar a condicional
        with self.builder.if_then(cond):
            self.builder.branch(loop_block)
        
        #resto do codigo?
    #end repita
   
    # CODEGENERATORS
    #$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
    #$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
    # ORCHESTRA

    def navigate(self, node):
        #preordem => pedaços do código antes de ir pros filhos
        if node.type == 'DECLARACAO_FUNCAO':
            self.declFuncao(node)
            return

        elif node.type == 'DECLARACAO_VARIAVEIS':
            self.declVariaveis(node)
            return
        
        elif node.type == 'SIMBOLO' and node.name == ':=':
            self.atribuicao(node)
            return
        
        elif node.type == 'RETORNA':
            self.retorna(node)
            return
        
        elif node.type == 'LEIA':
            self.leia(node)
            return
        
        elif node.type == 'ESCREVA':
            self.escreva(node)
            return
        
        elif node.type == 'CHAMADA_FUNCAO':
            self.callFunc(node)
            return
        
        elif node.type == 'SE':
            self.seEntao(node)
            return
        
        elif node.type == 'REPITA':
            self.repita(node)
            return

        # print(node.name)

        ##%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        for child in node.children:
            self.navigate(child)
        ##%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

        #posordem => pedaços de código dps de voltar dos filhos
    #end navigate


    def generate(self):
        self.navigate(self.tree)

        if 0:
            print('\n\nfuncs:')
            for f in self.funcoes:
                print(f)

            print('\nvars:')
            for i in self.variaveis:
                print(i)
                
        return self.module
    #end generate
#END CLASS CODEGEN


#########################################
#########################################
#########################################

def main(file=None):
    if file:
        argv[1] = file

    aux = argv[1].split('.')
    if aux[-1] != 'tpp':
      raise IOError("Not a .tpp file!")

    try: 
        tree, func, var = _tppsemantica.main(argv[1])        
        # print(RenderTree(tree, style=AsciiStyle()).by_attr())

        codegen = CodeGen(tree, func, var)
        mdl = codegen.generate()

        arquivo = open(argv[1] + '.ll', 'w')
        arquivo.write(str(mdl))
        arquivo.close()

    except Exception as e:
        print('Não foi possível continuar a compilação: A geração de código falhou...')
        # print(e)
        return None

    print('DONE')
#end main()

if __name__ == "__main__":
    main()