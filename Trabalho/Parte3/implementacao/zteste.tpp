inteiro: a[10]
inteiro: b

inteiro func1(inteiro:x, inteiro:y)
  inteiro: res[x]
  se (x <> y) então
    res := x + y
  senão
    res := x * y
  fim
  retorna(res)
fim

inteiro principal()
  inteiro: x,y
  leia(x)
  y := 5
  b := func1(x,y)
  escreva(b)
  a[9] := 10 + 2 + 5 * 2 / (10 - 5) + func1(x,y)
  retorna(0)
fim