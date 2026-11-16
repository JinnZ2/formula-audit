$( Hand-written for the kernel tests. Co-authored. CC0.
   One axiom with a disjoint-variable condition, and proofs that keep it or
   break it. $)
$c |- term wff = E. ( ) + $.
$v x y z $.
tx $f term x $.
ty $f term y $.
tz $f term z $.
tpl $a term ( x + y ) $.
weq $a wff x = y $.
$( x must be disjoint from y $)
${ $d x y $.  ax-ex $a |- E. x x = y $. $}
$( x := y, y := z, with $d y z in effect: allowed $)
${ $d y z $.  good $p |- E. y y = z $= ty tz ax-ex $. $}
$( the same $d stated twice: either line alone is enough $)
${ $d y z $.  $d z y $.  good2 $p |- E. y y = z $= ty tz ax-ex $. $}
$( the same proof with no $d in effect $)
no-dv $p |- E. y y = z $= ty tz ax-ex $.
$( x := y and y := y $)
same-var $p |- E. y y = y $= ty ty ax-ex $.
$( x := z and y := ( z + z ): the variable z is inside both $)
inside $p |- E. z z = ( z + z ) $= tz tz tz tpl ax-ex $.
