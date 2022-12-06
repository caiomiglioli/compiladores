import subprocess
from sys import argv, exit
import _tppcodegen as codegen

def main():
    # pegar nome do arquivo
    try:
        aux = argv[1].split('.')
    except:
        print('Arquivo inválido!')
        return

    # verificar extensão
    if aux[-1] != 'tpp':
        print('O arquivo selecionado não tem a extensao .tpp!')
        return

    #gerar o codigo ll
    try:
        codegen.main(argv[1])
    except:
        return

    file = str(argv[1])

    if len(argv) > 2 and argv[2]:
        executavel = str(argv[2])
    else:
        executavel = str(argv[1]) + '.o'

    # comandos necessarios para gerar o codigo
    commands = [
        'clang -emit-llvm -S io.c', 
        'llc -march=x86-64 -filetype=obj io.ll -o io.o', 
        'llvm-link ' + file + '.ll io.ll -o ' + file + '.bc', 
        'clang ' + file + '.bc -o ' + executavel, 
        'rm ' + file + '.bc'
    ]
    
    # rodo os comandos
    for command in commands:
        subprocess.run(command.split(' '))


if __name__ == "__main__":
    main()