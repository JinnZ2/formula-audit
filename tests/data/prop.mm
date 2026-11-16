$( Hand-written for the kernel tests. Co-authored. CC0.
   Implication only: two axioms and modus ponens. $)
$c ( ) -> wff |- $.
$v P Q R $.
wp $f wff P $.
wq $f wff Q $.
wr $f wff R $.
wi $a wff ( P -> Q ) $.
ax-1 $a |- ( P -> ( Q -> P ) ) $.
ax-2 $a |- ( ( P -> ( Q -> R ) ) -> ( ( P -> Q ) -> ( P -> R ) ) ) $.
${
  min $e |- P $.
  maj $e |- ( P -> Q ) $.
  mp $a |- Q $.
$}
$( P -> P, in five lines: ax-1 twice, ax-2 once, mp twice. $)
id $p |- ( P -> P ) $=
  wp wp wp wi wi  wp wp wi
  wp wp ax-1
  wp wp wp wi wp wi wi  wp wp wp wi wi wp wp wi wi
  wp wp wp wi ax-1
  wp wp wp wi wp ax-2
  mp mp $.
$( the same proof, compressed: wp = A; wi ax-1 ax-2 mp = B C D E; Z saves
   ( P -> P ), used again as F $)
idc $p |- ( P -> P ) $=
  ( wi ax-1 ax-2 mp ) AAABZBFAACAFABBAFBFBAFCAFADEE $.
$( an inference using its own hypothesis, and an earlier theorem $)
${
  a1i.1 $e |- P $.
  a1i $p |- ( Q -> P ) $= wp wq wp wi a1i.1 wp wq ax-1 mp $.
$}
idd $p |- ( Q -> ( P -> P ) ) $= wp wp wi wq wp id a1i $.
