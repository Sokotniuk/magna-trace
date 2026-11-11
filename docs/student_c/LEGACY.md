# Student C's earlier backend — removed from the tree

Student C first built a self-contained backend and console chat (`student_c/`). The independent
audit (finding **F13**, `docs/FINAL_BACKEND_AUDIT.md`) found that its numeric and error semantics
differ from the active backend and contract B2, so it must not be used as a demo fallback.

Decision **D40** removed that code (`student_c/backend`, `student_c/tests`, `student_c/harness`)
from the working tree. It is still in the Git history: the last commit that contains it is the
parent of the D40 commit. The notes in this folder are kept for history; paths inside them refer
to the old layout. Runtime Copilot instructions moved to `copilot/`, the read-only user script to
`devtools/oracle/`.
