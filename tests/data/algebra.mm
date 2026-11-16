$( algebra.mm -- a small hand-written database for the proposals -> kernel seam.
   Co-authored. CC0.

   Every $a below is GIVEN INPUT. The kernel gives an axiom no verdict; a PASS
   on a proof against this file says the proof follows from these axioms by
   the Metamath rules, and nothing about the axioms. They were written by hand
   for this repository and have not been reviewed by anyone else.

   Terms stand for real numbers. ( t / r ) and ( sqrt t ) are terms for every
   t and r, but an axiom speaks about them only where they have a value:
   division only for a non-zero divisor, sqrt only for 0 <_ t.
   ( t ^ n ) is given only for the numerals 0 to 9, with ( t ^ 0 ) = 1. $)

$c ( ) + - * / ^ sqrt -u = <_ -> /\ -. wff term |- $.
$c 0 1 2 3 4 5 6 7 8 9 $.

$( wff variables $)
$v ph ps ch $.
wph $f wff ph $.
wps $f wff ps $.
wch $f wff ch $.

$( term variables of the axiom schemes $)
$v t r s $.
tt $f term t $.
tr $f term r $.
ts $f term s $.

$( term variables a translated statement uses, in order $)
$v v0 v1 v2 v3 v4 v5 v6 v7 $.
tv0 $f term v0 $.
tv1 $f term v1 $.
tv2 $f term v2 $.
tv3 $f term v3 $.
tv4 $f term v4 $.
tv5 $f term v5 $.
tv6 $f term v6 $.
tv7 $f term v7 $.

$( ---- syntax ---- $)
n0 $a term 0 $.
n1 $a term 1 $.
n2 $a term 2 $.
n3 $a term 3 $.
n4 $a term 4 $.
n5 $a term 5 $.
n6 $a term 6 $.
n7 $a term 7 $.
n8 $a term 8 $.
n9 $a term 9 $.
tadd $a term ( t + r ) $.
tsub $a term ( t - r ) $.
tmul $a term ( t * r ) $.
tdiv $a term ( t / r ) $.
tpow $a term ( t ^ r ) $.
tsqrt $a term ( sqrt t ) $.
tneg $a term -u t $.
weq $a wff t = r $.
wle $a wff t <_ r $.
wn $a wff -. ph $.
wi $a wff ( ph -> ps ) $.
wa $a wff ( ph /\ ps ) $.

$( ---- propositional logic ---- $)
${
  min $e |- ph $.
  maj $e |- ( ph -> ps ) $.
  ax-mp $a |- ps $.
$}
ax-1 $a |- ( ph -> ( ps -> ph ) ) $.
ax-2 $a |- ( ( ph -> ( ps -> ch ) ) -> ( ( ph -> ps ) -> ( ph -> ch ) ) ) $.
ax-3 $a |- ( ( -. ph -> -. ps ) -> ( ps -> ph ) ) $.
ax-simpl $a |- ( ( ph /\ ps ) -> ph ) $.
ax-simpr $a |- ( ( ph /\ ps ) -> ps ) $.
ax-conj $a |- ( ph -> ( ps -> ( ph /\ ps ) ) ) $.

$( ---- equality ---- $)
eqid $a |- t = t $.
eqcom $a |- ( t = r -> r = t ) $.
eqtr $a |- ( ( t = r /\ r = s ) -> t = s ) $.
addeq1 $a |- ( t = r -> ( t + s ) = ( r + s ) ) $.
addeq2 $a |- ( t = r -> ( s + t ) = ( s + r ) ) $.
subeq1 $a |- ( t = r -> ( t - s ) = ( r - s ) ) $.
subeq2 $a |- ( t = r -> ( s - t ) = ( s - r ) ) $.
muleq1 $a |- ( t = r -> ( t * s ) = ( r * s ) ) $.
muleq2 $a |- ( t = r -> ( s * t ) = ( s * r ) ) $.
diveq1 $a |- ( t = r -> ( t / s ) = ( r / s ) ) $.
diveq2 $a |- ( t = r -> ( s / t ) = ( s / r ) ) $.
poweq1 $a |- ( t = r -> ( t ^ s ) = ( r ^ s ) ) $.
sqrteq $a |- ( t = r -> ( sqrt t ) = ( sqrt r ) ) $.
negeq $a |- ( t = r -> -u t = -u r ) $.
leeq1 $a |- ( t = r -> ( t <_ s -> r <_ s ) ) $.
leeq2 $a |- ( t = r -> ( s <_ t -> s <_ r ) ) $.

$( ---- field axioms for + - * / ---- $)
addcom $a |- ( t + r ) = ( r + t ) $.
addass $a |- ( ( t + r ) + s ) = ( t + ( r + s ) ) $.
add0 $a |- ( t + 0 ) = t $.
addneg $a |- ( t + -u t ) = 0 $.
subdef $a |- ( t - r ) = ( t + -u r ) $.
mulcom $a |- ( t * r ) = ( r * t ) $.
mulass $a |- ( ( t * r ) * s ) = ( t * ( r * s ) ) $.
mul1 $a |- ( t * 1 ) = t $.
distr $a |- ( t * ( r + s ) ) = ( ( t * r ) + ( t * s ) ) $.
divmul $a |- ( -. r = 0 -> ( ( t / r ) * r ) = t ) $.
ne01 $a |- -. 0 = 1 $.

$( ---- numerals ---- $)
df-2 $a |- 2 = ( 1 + 1 ) $.
df-3 $a |- 3 = ( 2 + 1 ) $.
df-4 $a |- 4 = ( 3 + 1 ) $.
df-5 $a |- 5 = ( 4 + 1 ) $.
df-6 $a |- 6 = ( 5 + 1 ) $.
df-7 $a |- 7 = ( 6 + 1 ) $.
df-8 $a |- 8 = ( 7 + 1 ) $.
df-9 $a |- 9 = ( 8 + 1 ) $.

$( ---- powers with a numeral exponent ---- $)
exp0 $a |- ( t ^ 0 ) = 1 $.
exp1 $a |- ( t ^ 1 ) = t $.
exp2 $a |- ( t ^ 2 ) = ( t * t ) $.
exp3 $a |- ( t ^ 3 ) = ( ( t ^ 2 ) * t ) $.
exp4 $a |- ( t ^ 4 ) = ( ( t ^ 3 ) * t ) $.
exp5 $a |- ( t ^ 5 ) = ( ( t ^ 4 ) * t ) $.
exp6 $a |- ( t ^ 6 ) = ( ( t ^ 5 ) * t ) $.
exp7 $a |- ( t ^ 7 ) = ( ( t ^ 6 ) * t ) $.
exp8 $a |- ( t ^ 8 ) = ( ( t ^ 7 ) * t ) $.
exp9 $a |- ( t ^ 9 ) = ( ( t ^ 8 ) * t ) $.

$( ---- order ---- $)
leid $a |- t <_ t $.
letr $a |- ( ( t <_ r /\ r <_ s ) -> t <_ s ) $.
letot $a |- ( -. t <_ r -> r <_ t ) $.
leasym $a |- ( ( t <_ r /\ r <_ t ) -> t = r ) $.
leadd $a |- ( t <_ r -> ( t + s ) <_ ( r + s ) ) $.
lemul $a |- ( ( 0 <_ t /\ 0 <_ r ) -> 0 <_ ( t * r ) ) $.
le01 $a |- 0 <_ 1 $.

$( ---- sqrt, only on 0 <_ t ---- $)
sqrtsq $a |- ( 0 <_ t -> ( ( sqrt t ) * ( sqrt t ) ) = t ) $.
sqrtge0 $a |- ( 0 <_ t -> 0 <_ ( sqrt t ) ) $.
