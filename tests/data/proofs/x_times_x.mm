$( Hand-written proof for the seam tests. Co-authored. CC0.
   ( v0 ^ 2 ) = ( v0 * v0 ) is axiom exp2; eqcom turns it round; ax-mp detaches.
   The two domain bounds are stated and not needed. $)
${
  dom.1 $e |- 0 <_ v0 $.
  dom.2 $e |- v0 <_ 1 $.
  target $p |- ( v0 * v0 ) = ( v0 ^ 2 ) $=
    tv0 n2 tpow  tv0 tv0 tmul  weq
    tv0 tv0 tmul  tv0 n2 tpow  weq
    tv0 exp2
    tv0 n2 tpow  tv0 tv0 tmul  eqcom
    ax-mp $.
$}
