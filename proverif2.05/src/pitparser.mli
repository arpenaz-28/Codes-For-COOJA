type token =
  | CHOICE
  | STAR
  | COMMA
  | LPAREN
  | RPAREN
  | LBRACKET
  | RBRACKET
  | BAR
  | SEMI
  | NEW
  | OUT
  | IN
  | AT
  | IDENT of (Pitptree.ident)
  | TAG of (Pitptree.ident)
  | STRING of (Pitptree.ident)
  | PROJECTION of (Pitptree.ident)
  | UNDERSCORE of (Parsing_helper.extent)
  | INT of (int)
  | REPL
  | IF
  | THEN
  | ELSE
  | EQUAL
  | FUN
  | EQUATION
  | REDUCTION
  | PREDICATE
  | PROCESS
  | SLASH
  | DOT
  | EOF
  | LET
  | QUERY
  | BEFORE
  | PUTBEGIN
  | NONINTERF
  | EVENT
  | NOT
  | ELIMTRUE
  | FREE
  | SUCHTHAT
  | CLAUSES
  | RED
  | EQUIV
  | EQUIVEQ
  | WEDGE
  | DIFF
  | COLON
  | NOUNIF
  | SELECT
  | PHASE
  | BARRIER
  | AMONG
  | WEAKSECRET
  | PARAM
  | ORTEXT
  | FAIL
  | LESS
  | GREATER
  | GEQ
  | PLUS
  | MINUS
  | TYPE
  | SET
  | FORALL
  | CONST
  | INJEVENT
  | OR
  | CHANNEL
  | LETFUN
  | DEFINE
  | EXPAND
  | YIELD
  | LEQ
  | PROBA
  | LETPROBA
  | OPTIMIF
  | ISCST
  | COUNT
  | FLOAT of (float)
  | LBRACE
  | RBRACE
  | PROOF
  | IMPLEMENTATION
  | EQUIVALENCE
  | OTHERWISE
  | FOREACH
  | DO
  | SECRET
  | PUBLICVARS
  | RANDOM
  | LEFTARROW
  | POWER
  | LEMMA
  | AXIOM
  | RESTRICTION
  | FOR
  | TABLE
  | INSERT
  | GET

val all :
  (Lexing.lexbuf  -> token) -> Lexing.lexbuf -> Pitptree.tdecl list * Pitptree.tprocess_e * Pitptree.tprocess_e option
val lib :
  (Lexing.lexbuf  -> token) -> Lexing.lexbuf -> Pitptree.tdecl list
val permut :
  (Lexing.lexbuf  -> token) -> Lexing.lexbuf -> Pitptree.ident list list
val order :
  (Lexing.lexbuf  -> token) -> Lexing.lexbuf -> Pitptree.ident list
val term :
  (Lexing.lexbuf  -> token) -> Lexing.lexbuf -> Pitptree.term_e
